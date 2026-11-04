-- Enforce the agreed appointment states and 30-minute booking conflicts.
-- This migration adds no columns and leaves existing RLS policies in place.

BEGIN;

CREATE EXTENSION IF NOT EXISTS btree_gist;

ALTER TABLE public.appointments ENABLE ROW LEVEL SECURITY;

REVOKE ALL PRIVILEGES ON TABLE public.appointments FROM PUBLIC, anon, authenticated;
REVOKE SELECT (id, patient_id, doctor_id, appointment_date, appointment_time, reason, status, created_at),
       INSERT (id, patient_id, doctor_id, appointment_date, appointment_time, reason, status, created_at),
       UPDATE (id, patient_id, doctor_id, appointment_date, appointment_time, reason, status, created_at),
       REFERENCES (id, patient_id, doctor_id, appointment_date, appointment_time, reason, status, created_at)
    ON TABLE public.appointments FROM PUBLIC, anon, authenticated;
GRANT SELECT ON TABLE public.appointments TO authenticated;
GRANT INSERT (
    id,
    patient_id,
    doctor_id,
    appointment_date,
    appointment_time,
    reason,
    status,
    created_at
) ON TABLE public.appointments TO authenticated;
GRANT UPDATE (status) ON TABLE public.appointments TO authenticated;

-- This returns only whether a caller may book with a doctor. It does not expose
-- profile fields and is usable only for the authenticated caller's own patient ID.
CREATE OR REPLACE FUNCTION public.patient_can_book_with_doctor(
    p_patient_id uuid,
    p_doctor_id uuid
)
RETURNS boolean
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = ''
AS $$
    SELECT p_patient_id = auth.uid()
       AND EXISTS (
            SELECT 1
            FROM public.profiles AS patient_profile
            WHERE patient_profile.id = auth.uid()
              AND patient_profile.role = 'patient'
       )
       AND EXISTS (
            SELECT 1
            FROM public.profiles AS doctor_profile
            WHERE doctor_profile.id = p_doctor_id
              AND doctor_profile.role = 'doctor'
       );
$$;

-- Own the definer function with Supabase's privileged database role so the
-- profile RLS policy does not hide the target doctor's role from this check.
ALTER FUNCTION public.patient_can_book_with_doctor(uuid, uuid) OWNER TO postgres;
REVOKE ALL ON FUNCTION public.patient_can_book_with_doctor(uuid, uuid)
    FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.patient_can_book_with_doctor(uuid, uuid)
    TO authenticated;

DROP POLICY IF EXISTS medifront_appointments_authenticated_select
    ON public.appointments;
CREATE POLICY medifront_appointments_authenticated_select
    ON public.appointments AS PERMISSIVE FOR SELECT TO authenticated
    USING (true);

DROP POLICY IF EXISTS medifront_appointments_role_select
    ON public.appointments;
CREATE POLICY medifront_appointments_role_select
    ON public.appointments AS RESTRICTIVE FOR SELECT TO authenticated
    USING (
        (
            patient_id = auth.uid()
            AND EXISTS (
                SELECT 1 FROM public.profiles AS patient_profile
                WHERE patient_profile.id = auth.uid()
                  AND patient_profile.role = 'patient'
            )
        )
        OR (
            doctor_id = auth.uid()
            AND EXISTS (
                SELECT 1 FROM public.profiles AS doctor_profile
                WHERE doctor_profile.id = auth.uid()
                  AND doctor_profile.role = 'doctor'
            )
        )
        OR EXISTS (
            SELECT 1 FROM public.profiles AS staff_profile
            WHERE staff_profile.id = auth.uid()
              AND staff_profile.role IN ('receptionist', 'admin')
        )
    );

DROP POLICY IF EXISTS medifront_appointments_authenticated_insert
    ON public.appointments;
CREATE POLICY medifront_appointments_authenticated_insert
    ON public.appointments AS PERMISSIVE FOR INSERT TO authenticated
    WITH CHECK (true);

DROP POLICY IF EXISTS medifront_appointments_patient_insert
    ON public.appointments;
CREATE POLICY medifront_appointments_patient_insert
    ON public.appointments AS RESTRICTIVE FOR INSERT TO authenticated
    WITH CHECK (
        patient_id = auth.uid()
        AND status = 'scheduled'
        AND public.patient_can_book_with_doctor(patient_id, doctor_id)
    );

DROP POLICY IF EXISTS medifront_appointments_authenticated_update
    ON public.appointments;
CREATE POLICY medifront_appointments_authenticated_update
    ON public.appointments AS PERMISSIVE FOR UPDATE TO authenticated
    USING (true)
    WITH CHECK (true);

DROP POLICY IF EXISTS medifront_appointments_role_update
    ON public.appointments;
CREATE POLICY medifront_appointments_role_update
    ON public.appointments AS RESTRICTIVE FOR UPDATE TO authenticated
    USING (
        (
            patient_id = auth.uid()
            AND status IN ('scheduled', 'confirmed')
            AND EXISTS (
                SELECT 1 FROM public.profiles AS patient_profile
                WHERE patient_profile.id = auth.uid()
                  AND patient_profile.role = 'patient'
            )
        )
        OR EXISTS (
            SELECT 1 FROM public.profiles AS staff_profile
            WHERE staff_profile.id = auth.uid()
              AND staff_profile.role IN ('receptionist', 'admin')
        )
    )
    WITH CHECK (
        (
            patient_id = auth.uid()
            AND status = 'cancelled'
            AND EXISTS (
                SELECT 1 FROM public.profiles AS patient_profile
                WHERE patient_profile.id = auth.uid()
                  AND patient_profile.role = 'patient'
            )
        )
        OR (
            status IN ('scheduled', 'confirmed', 'cancelled', 'completed')
            AND EXISTS (
                SELECT 1 FROM public.profiles AS staff_profile
                WHERE staff_profile.id = auth.uid()
                  AND staff_profile.role IN ('receptionist', 'admin')
            )
        )
    );

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM public.appointments
        WHERE status IS NULL
           OR status NOT IN ('scheduled', 'confirmed', 'cancelled', 'completed')
    ) THEN
        RAISE EXCEPTION
            'appointments contains NULL or unsupported statuses; normalize rows before applying this migration';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conrelid = 'public.appointments'::regclass
          AND conname = 'medifront_appointments_status_check'
    ) THEN
        ALTER TABLE public.appointments
            ADD CONSTRAINT medifront_appointments_status_check
            CHECK (
                status IS NOT NULL
                AND status IN ('scheduled', 'confirmed', 'cancelled', 'completed')
            );
    END IF;

    IF EXISTS (
        SELECT 1
        FROM public.appointments AS first_appointment
        JOIN public.appointments AS second_appointment
          ON first_appointment.id < second_appointment.id
         AND first_appointment.patient_id = second_appointment.patient_id
        WHERE first_appointment.status IN ('scheduled', 'confirmed')
          AND second_appointment.status IN ('scheduled', 'confirmed')
          AND tsrange(
                first_appointment.appointment_date + first_appointment.appointment_time,
                first_appointment.appointment_date + first_appointment.appointment_time + INTERVAL '30 minutes',
                '[)'
              ) && tsrange(
                second_appointment.appointment_date + second_appointment.appointment_time,
                second_appointment.appointment_date + second_appointment.appointment_time + INTERVAL '30 minutes',
                '[)'
              )
    ) THEN
        RAISE EXCEPTION
            'existing active appointments overlap for a patient; resolve conflicts before applying this migration';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conrelid = 'public.appointments'::regclass
          AND conname = 'medifront_appointments_patient_no_overlap'
    ) THEN
        ALTER TABLE public.appointments
            ADD CONSTRAINT medifront_appointments_patient_no_overlap
            EXCLUDE USING gist (
                patient_id WITH =,
                (tsrange(
                    appointment_date + appointment_time,
                    appointment_date + appointment_time + INTERVAL '30 minutes',
                    '[)'
                )) WITH &&
            )
            WHERE (status IN ('scheduled', 'confirmed'));
    END IF;

    IF EXISTS (
        SELECT 1
        FROM public.appointments AS first_appointment
        JOIN public.appointments AS second_appointment
          ON first_appointment.id < second_appointment.id
         AND first_appointment.doctor_id = second_appointment.doctor_id
        WHERE first_appointment.status IN ('scheduled', 'confirmed')
          AND second_appointment.status IN ('scheduled', 'confirmed')
          AND tsrange(
                first_appointment.appointment_date + first_appointment.appointment_time,
                first_appointment.appointment_date + first_appointment.appointment_time + INTERVAL '30 minutes',
                '[)'
              ) && tsrange(
                second_appointment.appointment_date + second_appointment.appointment_time,
                second_appointment.appointment_date + second_appointment.appointment_time + INTERVAL '30 minutes',
                '[)'
              )
    ) THEN
        RAISE EXCEPTION
            'existing active appointments overlap for a doctor; resolve conflicts before applying this migration';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conrelid = 'public.appointments'::regclass
          AND conname = 'medifront_appointments_doctor_no_overlap'
    ) THEN
        ALTER TABLE public.appointments
            ADD CONSTRAINT medifront_appointments_doctor_no_overlap
            EXCLUDE USING gist (
                doctor_id WITH =,
                (tsrange(
                    appointment_date + appointment_time,
                    appointment_date + appointment_time + INTERVAL '30 minutes',
                    '[)'
                )) WITH &&
            )
            WHERE (status IN ('scheduled', 'confirmed'));
    END IF;
END;
$$;

COMMIT;
