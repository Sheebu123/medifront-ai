export function AuthField({
  label,
  name,
  type = 'text',
  placeholder,
  autoComplete,
  required = true,
}: {
  label: string
  name: string
  type?: string
  placeholder: string
  autoComplete?: string
  required?: boolean
}) {
  return (
    <label className="block text-sm font-semibold text-[#52687c]">
      {label}
      <input className="mt-2 block h-11 w-full rounded-lg border border-[#dbe6ed] bg-white px-3 text-sm font-normal text-[#102a43] outline-none transition focus:border-[#2878d7] focus:ring-4 focus:ring-[#2878d7]/10" name={name} type={type} placeholder={placeholder} autoComplete={autoComplete} required={required} />
    </label>
  )
}

export function AuthError({ message }: { message: string }) {
  return <p role="alert" className="rounded-lg border border-[#f4c9cc] bg-[#fff3f3] px-3 py-2.5 text-sm text-[#b5313c]">{message}</p>
}

export function AuthSubmit({ children, loading }: { children: React.ReactNode; loading: boolean }) {
  return <button className="flex h-11 w-full items-center justify-center rounded-lg bg-[#2878d7] px-4 text-sm font-bold text-white transition hover:bg-[#1f68bf] disabled:cursor-not-allowed disabled:opacity-60" type="submit" disabled={loading}>{loading ? 'Please wait...' : children}</button>
}