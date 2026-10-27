"use client"

import { useEffect, useMemo, useState } from "react"
import type { Appointment } from "@/lib/appointments/server"
import { LogoutButton } from "@/components/auth/logout-button"
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  BarChart3,
  Bell,
  CalendarDays,
  Check,
  ChevronDown,
  CircleHelp,
  Clock3,
  FileText,
  HeartPulse,
  Hospital,
  Languages,
  LayoutDashboard,
  Map,
  Menu,
  MessageCircle,
  MoreHorizontal,
  Navigation,
  Search,
  Settings,
  ShieldCheck,
  Stethoscope,
  Moon,
  Sun,
  Users,
  Video,
  X,
  Zap,
} from "lucide-react"

type ViewKey = "Dashboard" | "Patient Check-In" | "AI Receptionist" | "Appointments" | "Queue Management" | "Navigation" | "Vision Monitor" | "Alerts" | "Patients" | "Doctors" | "Analytics" | "Settings" | "Kiosk"

type IconType = typeof LayoutDashboard

const navGroups: { label: string; items: { label: ViewKey; icon: IconType }[] }[] = [
  { label: "Operations", items: [
    { label: "Dashboard", icon: LayoutDashboard },
    { label: "Patient Check-In", icon: ShieldCheck },
    { label: "AI Receptionist", icon: MessageCircle },
    { label: "Appointments", icon: CalendarDays },
    { label: "Queue Management", icon: Clock3 },
  ] },
  { label: "Hospital tools", items: [
    { label: "Navigation", icon: Map },
    { label: "Vision Monitor", icon: Video },
    { label: "Alerts", icon: AlertTriangle },
    { label: "Patients", icon: Users },
    { label: "Doctors", icon: Stethoscope },
    { label: "Analytics", icon: BarChart3 },
  ] },
]

const kpis = [
  { label: "Patients today", value: "1,284", change: "+8.4%", note: "vs yesterday", icon: Users, tone: "blue" },
  { label: "Checked in", value: "936", change: "73%", note: "of today’s patients", icon: ShieldCheck, tone: "teal" },
  { label: "Waiting patients", value: "87", change: "Currently", note: "in active queues", icon: Clock3, tone: "amber" },
  { label: "Average wait time", value: "18 min", change: "−4 min", note: "from yesterday", icon: Activity, tone: "green" },
  { label: "Appointments today", value: "342", change: "28", note: "upcoming", icon: CalendarDays, tone: "purple" },
  { label: "Active alerts", value: "3", change: "1 urgent", note: "needs attention", icon: AlertTriangle, tone: "red" },
]

const queues = [
  { department: "General Medicine", doctor: "Dr. Arjun Mehta", waiting: 21, token: "G-208", eta: "32 min", status: "Busy", progress: 72 },
  { department: "Cardiology", doctor: "Dr. Raj Sharma", waiting: 12, token: "C-104", eta: "24 min", status: "Normal", progress: 48 },
  { department: "Orthopedics", doctor: "Dr. Imran Khan", waiting: 9, token: "O-067", eta: "18 min", status: "Normal", progress: 38 },
  { department: "Pediatrics", doctor: "Dr. Neha Kapoor", waiting: 18, token: "P-146", eta: "27 min", status: "Busy", progress: 63 },
  { department: "Emergency", doctor: "Dr. Vikram Singh", waiting: 4, token: "E-031", eta: "6 min", status: "Priority", progress: 20 },
]

function StatusBadge({ children, tone = "neutral" }: { children: React.ReactNode; tone?: string }) {
  return <span className={`status-badge status-${tone}`}>{children}</span>
}

function PageHeader({ title, eyebrow = "MediCare City Hospital", action }: { title: string; eyebrow?: string; action?: React.ReactNode }) {
  return <div className="page-header"><div><p className="eyebrow">{eyebrow}</p><h1>{title}</h1></div>{action}</div>
}

function DashboardView({ onNavigate, appointments }: { onNavigate: (view: ViewKey) => void; appointments: Appointment[] }) {
  return <>
    <PageHeader title="Hospital Front Desk Dashboard" action={<button className="button button-primary" onClick={() => onNavigate("Patient Check-In")}><ShieldCheck size={16} /> Start check-in</button>} />
    <p className="page-subtitle">Real-time overview of patient reception, appointments, queues and alerts.</p>
    <div className="urgent-banner"><div className="urgent-icon"><AlertTriangle size={19} /></div><div><strong>Urgent staff attention required</strong><p>Potential urgent situation detected in Reception Area 02 · requires staff verification</p></div><button className="button button-danger" onClick={() => onNavigate("Alerts")}>Review alert <ArrowRight size={15} /></button></div>
    <div className="kpi-grid">{kpis.map((kpi) => { const Icon = kpi.icon; return <div className="kpi-card" key={kpi.label}><div className={`kpi-icon ${kpi.tone}`}><Icon size={18} /></div><div className="kpi-label">{kpi.label}</div><div className="kpi-value">{kpi.value}</div><div className="kpi-meta"><span className={`kpi-change ${kpi.tone}`}>{kpi.change}</span><span>{kpi.note}</span></div></div> })}</div>
    <div className="content-grid two-col"><section className="panel queue-panel"><div className="panel-heading"><div><h2>Live patient queue</h2><p>Updated just now · 5 departments active</p></div><button className="button button-ghost" onClick={() => onNavigate("Queue Management")}>Manage queue <ArrowRight size={15} /></button></div><div className="queue-list">{queues.map((queue) => <div className="queue-row" key={queue.department}><div className="department-mark">{queue.department.slice(0, 1)}</div><div className="queue-main"><div className="queue-title"><strong>{queue.department}</strong><StatusBadge tone={queue.status === "Priority" ? "red" : queue.status === "Busy" ? "amber" : "green"}>{queue.status}</StatusBadge></div><span>{queue.doctor}</span><div className="queue-progress"><span style={{ width: `${queue.progress}%` }} /></div></div><div className="queue-stat"><strong>{queue.waiting}</strong><span>waiting</span></div><div className="queue-stat hide-mobile"><strong>{queue.token}</strong><span>current token</span></div><div className="queue-stat eta"><strong>{queue.eta}</strong><span>estimated wait</span></div><button className="icon-button" aria-label={`More options for ${queue.department}`}><MoreHorizontal size={17} /></button></div>)}</div></section>
      <AIReceptionist onNavigate={onNavigate} />
    </div>
    <section className="panel appointments-panel"><div className="panel-heading"><div><h2>Today&apos;s appointments</h2><p>Tuesday, 16 September 2026 · 342 scheduled appointments</p></div><button className="button button-ghost" onClick={() => onNavigate("Appointments")}>View all appointments <ArrowRight size={15} /></button></div><div className="table-wrap"><table><thead><tr>{["Time", "Patient", "Doctor", "Department", "Type", "Status", ""].map((head) => <th key={head}>{head}</th>)}</tr></thead><tbody>{appointments.length === 0 ? <tr><td colSpan={7} className="text-center">No appointments found.</td></tr> : appointments.map((appointment) => <tr key={appointment.id}><td>{appointment.appointment_date} {appointment.appointment_time}</td><td>{appointment.patient_id || "—"}</td><td>{appointment.doctor_id || "—"}</td><td>—</td><td>{appointment.reason || "—"}</td><td><StatusBadge tone={appointment.status.toLowerCase().includes("wait") ? "amber" : appointment.status.toLowerCase().includes("cancel") ? "red" : "blue"}>{appointment.status}</StatusBadge></td><td><button className="icon-button" aria-label={`More actions for appointment ${appointment.id}`}><MoreHorizontal size={17} /></button></td></tr>)}</tbody></table></div></section>
  </>
}

function AIReceptionist({ onNavigate }: { onNavigate: (view: ViewKey) => void }) {
  const [message, setMessage] = useState("")
  const [sent, setSent] = useState(false)
  return <section className="panel ai-panel"><div className="panel-heading"><div className="ai-title"><div className="ai-avatar"><MessageCircle size={18} /></div><div><h2>AI Receptionist</h2><p>Natural language patient assistance</p></div></div><StatusBadge tone="green"><span className="live-dot" /> Online</StatusBadge></div><div className="chat-window"><div className="chat-message assistant">Hello! Welcome to MediFront AI Hospital. How can I help you today?</div><div className="chat-message patient">I have an appointment with Dr. Sharma at 11 AM.</div><div className="chat-message assistant">I found your appointment in Cardiology at 11:00 AM. Would you like to check in?</div>{sent && <div className="chat-message patient">{message}</div>}</div><div className="chat-actions"><button className="button button-soft" onClick={() => onNavigate("Patient Check-In")}>Check in</button><button className="button button-outline">Change appointment</button><button className="button button-outline" onClick={() => onNavigate("Appointments")}>View appointment</button><button className="button button-outline" onClick={() => setSent(true)}>Talk to staff</button></div><div className="chat-compose"><input value={message} onChange={(e) => setMessage(e.target.value)} placeholder="Type a patient request..." onKeyDown={(e) => { if (e.key === "Enter" && message.trim()) { setSent(true); setMessage("") } }} /><button className="icon-button filled" aria-label="Send message" onClick={() => { if (message.trim()) { setSent(true); setMessage("") } }}><ArrowRight size={16} /></button></div><div className="ai-metrics"><div><strong>428</strong><span>requests today</span></div><div><strong>392</strong><span>resolved by AI</span></div><div><strong>1.8s</strong><span>avg response</span></div></div></section>
}

function GenericView({ view, onNavigate }: { view: ViewKey; onNavigate: (view: ViewKey) => void }) {
  const descriptions: Record<string, string> = { "Patient Check-In": "Verify patients, generate tokens and guide them to their appointment.", "AI Receptionist": "Assist patients with appointments, directions and staff handoff.", "Appointments": "Manage the hospital schedule, rescheduling and appointment status.", "Queue Management": "Monitor department queues and keep wait times moving.", Navigation: "Help patients find departments with clear indoor directions.", "Vision Monitor": "Review AI-assisted occupancy and queue observations.", Alerts: "Review safety signals and coordinate staff verification.", Patients: "Search front-desk patient records and upcoming visits.", Doctors: "View doctor availability, rooms and department load.", Analytics: "Understand reception performance across the hospital.", Settings: "Configure hospital, AI, vision and notification preferences.", Kiosk: "Launch the patient-facing touchscreen experience." }
  return <><PageHeader title={view} action={view === "Alerts" ? <button className="button button-danger" onClick={() => onNavigate("Vision Monitor")}><Video size={16} /> View camera</button> : <button className="button button-primary"><Zap size={16} /> New action</button>} /><p className="page-subtitle">{descriptions[view]}</p><div className="feature-grid"><div className="panel feature-hero"><div className="feature-hero-icon"><HeartPulse size={24} /></div><h2>{view === "Alerts" ? "AI-assisted safety signals" : `${view} workspace`}</h2><p>{view === "Alerts" ? "Potential urgent situations are surfaced for trained staff to verify. AI observations never replace clinical judgment." : "This operational workspace is ready for your hospital team. Connect your backend APIs when moving from prototype to production."}</p><div className="feature-actions"><button className="button button-primary" onClick={() => onNavigate("Dashboard")}>Return to dashboard <ArrowRight size={15} /></button><button className="button button-outline" onClick={() => onNavigate("Kiosk")}>Open kiosk mode</button></div></div><div className="panel summary-panel"><h2>Today at a glance</h2>{[["Active patients", "936", "green"], ["Waiting across queues", "87", "amber"], ["Staff notifications", "3", "red"], ["Systems status", "Operational", "blue"]].map(([label, value, tone]) => <div className="summary-row" key={label}><span>{label}</span><strong className={`text-${tone}`}>{value}</strong></div>)}</div></div><div className="content-grid two-col"><section className="panel"><div className="panel-heading"><div><h2>Operational updates</h2><p>Fictional demo data from MediCare City Hospital</p></div><button className="icon-button"><MoreHorizontal size={17} /></button></div><div className="update-list">{["Cardiology queue is moving 12% faster than yesterday", "3 new appointments confirmed for the afternoon", "Vision monitor checked Reception Area 01", "Staff handoff queue has 3 people waiting"].map((item, index) => <div className="update-item" key={item}><div className={`update-icon tone-${index}`}><Check size={15} /></div><div><strong>{item}</strong><span>{index + 1} hour{index ? "s" : ""} ago · MediFront system</span></div></div>)}</div></section><section className="panel safety-note"><div className="note-icon"><CircleHelp size={20} /></div><h2>Safety by design</h2><p>AI receptionist and vision features provide assistance signals only. Clinical assessment and final decisions always belong to qualified hospital staff.</p><button className="button button-outline" onClick={() => onNavigate("Settings")}>Review safety settings <ArrowRight size={15} /></button></section></div></>
}

function KioskView({ onNavigate }: { onNavigate: (view: ViewKey) => void }) {
  const actions = [["Check In", ShieldCheck], ["Book Appointment", CalendarDays], ["Find My Doctor", Stethoscope], ["Hospital Navigation", Navigation], ["Talk to AI Assistant", MessageCircle], ["Emergency Assistance", AlertTriangle]] as const
  return <div className="kiosk-shell"><div className="kiosk-top"><div className="brand-mark large"><Hospital size={22} /></div><div><strong>MEDIFRONT <span>AI</span></strong><small>Patient self-service kiosk</small></div><div className="kiosk-tools"><button className="button button-outline"><Languages size={16} /> English <ChevronDown size={14} /></button><button className="icon-button" aria-label="Close kiosk" onClick={() => onNavigate("Dashboard")}><X size={18} /></button></div></div><div className="kiosk-content"><div className="kiosk-welcome"><p className="eyebrow">MediCare City Hospital</p><h1>Welcome to MediFront AI</h1><p>How can we help you today?</p></div><div className="kiosk-actions">{actions.map(([label, Icon]) => <button key={label} className={`kiosk-action ${label === "Emergency Assistance" ? "emergency" : ""}`} onClick={() => label === "Check In" ? onNavigate("Patient Check-In") : undefined}><Icon size={30} /><span>{label}</span><ArrowRight size={18} /></button>)}</div><div className="kiosk-footer"><span><AccessibilityIcon /> Accessibility options</span><span><ShieldCheck size={15} /> Your information is private and secure</span></div></div></div>
}

function AccessibilityIcon() { return <span className="accessibility-icon">A</span> }

export default function MediFrontDashboard({ appointments = [] }: { appointments?: Appointment[] }) {
  const [activeView, setActiveView] = useState<ViewKey>("Dashboard")
  const [mobileNav, setMobileNav] = useState(false)
  const [search, setSearch] = useState("")
  const [profileMenuOpen, setProfileMenuOpen] = useState(false)
  const [theme, setTheme] = useState<"light" | "dark">("light")
  useEffect(() => {
    const savedTheme = window.localStorage.getItem("medifront-theme")
    if (savedTheme === "dark" || savedTheme === "light") setTheme(savedTheme)
  }, [])
  useEffect(() => {
    document.documentElement.dataset.theme = theme
    window.localStorage.setItem("medifront-theme", theme)
  }, [theme])
  const nav = (view: ViewKey) => { setActiveView(view); setMobileNav(false) }
  const isKiosk = activeView === "Kiosk"
  const filteredNav = useMemo(() => navGroups.map((group) => ({ ...group, items: group.items.filter((item) => item.label.toLowerCase().includes(search.toLowerCase())) })).filter((group) => group.items.length), [search])
  if (isKiosk) return <KioskView onNavigate={nav} />
  return <div className="app-shell"><aside className={`sidebar ${mobileNav ? "open" : ""}`}><div className="brand"><div className="brand-mark"><Hospital size={19} /></div><div><strong>MEDIFRONT <span>AI</span></strong><small>Hospital operations</small></div><button className="mobile-close icon-button" onClick={() => setMobileNav(false)} aria-label="Close navigation"><X size={18} /></button></div><div className="sidebar-search"><Search size={15} /><input placeholder="Search menu" value={search} onChange={(e) => setSearch(e.target.value)} /></div><nav>{filteredNav.map((group) => <div className="nav-group" key={group.label}><p>{group.label}</p>{group.items.map(({ label, icon: Icon }) => <button key={label} className={`nav-item ${activeView === label ? "active" : ""}`} onClick={() => nav(label)}><Icon size={17} /><span>{label}</span>{label === "Alerts" && <span className="nav-count">3</span>}</button>)}</div>)}<div className="nav-group"><p>System</p><button className={`nav-item ${activeView === "Settings" ? "active" : ""}`} onClick={() => nav("Settings")}><Settings size={17} /><span>Settings</span></button><button className="nav-item" onClick={() => nav("Kiosk")}><LayoutDashboard size={17} /><span>Open kiosk mode</span></button></div></nav><div className="sidebar-bottom"><div className="system-status"><span className="live-dot" /><div><strong>Systems operational</strong><span>All services healthy</span></div></div><div className="profile"><div className="avatar">AS</div><div><strong>Dr. Ananya Sharma</strong><span>Hospital administrator</span></div><MoreHorizontal size={17} /></div></div></aside><div className={`sidebar-overlay ${mobileNav ? "show" : ""}`} onClick={() => setMobileNav(false)} /><main className="main"><header className="topbar"><div className="topbar-left"><button className="menu-button icon-button" onClick={() => setMobileNav(true)} aria-label="Open navigation"><Menu size={20} /></button><div className="crumb"><span>MediCare City Hospital</span><ArrowRight size={13} /><strong>{activeView}</strong></div></div><div className="topbar-actions"><div className="global-search"><Search size={16} /><input placeholder="Search patients, appointments..." /></div><button className="language-button"><Languages size={16} /> EN <ChevronDown size={13} /></button><button className="icon-button notification" aria-label="Notifications"><Bell size={18} /><span>3</span></button><div className="profile-menu"><button className="top-profile" aria-expanded={profileMenuOpen} aria-haspopup="menu" onClick={() => setProfileMenuOpen((open) => !open)}><div className="avatar small">AS</div><div><strong>Good morning, Dr. Sharma</strong><span>Tuesday, 16 September 2026</span></div><ChevronDown size={15} /></button>{profileMenuOpen && <div className="profile-popover" role="menu"><div className="profile-menu-label">Account</div><button className="profile-menu-item" role="menuitem"><Users size={15} /> Profile</button><button className="profile-menu-item" role="menuitem" onClick={() => setTheme(theme === "light" ? "dark" : "light")}>{theme === "light" ? <Moon size={15} /> : <Sun size={15} />} {theme === "light" ? "Dark mode" : "Light mode"}</button><div className="profile-menu-divider" /><LogoutButton /></div>}</div></div></header><div className="main-content">{activeView === "Dashboard" ? <DashboardView onNavigate={nav} appointments={appointments} /> : <GenericView view={activeView} onNavigate={nav} />}</div><div className="mobile-bottom-nav">{[{ label: "Dashboard", icon: LayoutDashboard }, { label: "Appointments", icon: CalendarDays }, { label: "Alerts", icon: AlertTriangle }, { label: "Kiosk", icon: Hospital }].map(({ label, icon: Icon }) => <button key={label} className={activeView === label ? "active" : ""} onClick={() => nav(label as ViewKey)}><Icon size={18} /><span>{label}</span></button>)}</div></main></div>
}
