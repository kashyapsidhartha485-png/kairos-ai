'use client';

import { useState, useEffect, useRef } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import api from '@/lib/apiClient';

interface PatientCard { name: string; age: number; blood_group: string; conditions?: string; allergies?: string; medications?: string; emergency_contact_name: string; emergency_contact_phone: string; }
interface HospitalCheck { name: string; status: string; method?: string; }
interface Dashboard { ambulance_id: string; driver_name: string; status: string; emergency_id?: string; patient?: PatientCard; unidentified_notes?: string; pickup_lat?: number; pickup_lng?: number; pickup_nav_link?: string; pickup_directions_link?: string; ambulance_lat?: number; ambulance_lng?: number; prep_instructions?: string[]; hospital_name?: string; hospital_address?: string; hospital_phone?: string; hospital_lat?: number; hospital_lng?: number; hospital_nav_link?: string; hospital_directions_link?: string; scoring_reason?: string; unread_notifications?: number; }
interface RoutingStatus { routing_status: string; hospitals_checked: HospitalCheck[]; chosen_hospital?: any; }

const NAV_ITEMS = [
  { label: 'Dashboard', icon: '⊞', id: 'dashboard' },
  { label: 'Patient Details', icon: '👤', id: 'patient' },
  { label: 'Vitals & Condition', icon: '📈', id: 'vitals' },
  { label: 'Hospital Finder', icon: '🏥', id: 'hospital' },
  { label: 'Navigation', icon: '🧭', id: 'nav' },
  { label: 'History', icon: '📋', id: 'history' },
];

export default function DriverDashboard() {
  const { id } = useParams<{ id: string }>();
  const ambulanceId = id || 'AMB-001';

  const [dashboard, setDashboard] = useState<Dashboard | null>(null);
  const [routing, setRouting] = useState<RoutingStatus | null>(null);
  const [activeNav, setActiveNav] = useState('dashboard');
  const [conditionForm, setConditionForm] = useState({ symptoms: '', vitals: '', consciousness_level: '', visible_injuries: '' });
  const [conditionSubmitted, setConditionSubmitted] = useState(false);
  const [conditionLoading, setConditionLoading] = useState(false);
  const [isComplete, setIsComplete] = useState(false);
  const [flashAlert, setFlashAlert] = useState(false);
  // Simulation
  const [simStatus, setSimStatus] = useState<any>(null);
  const [simRunning, setSimRunning] = useState(false);
  const [simLoading, setSimLoading] = useState(false);
  const pollingRef = useRef<NodeJS.Timeout | null>(null);
  const routingRef = useRef<NodeJS.Timeout | null>(null);
  const simRef = useRef<NodeJS.Timeout | null>(null);
  const prevStatusRef = useRef<string | null>(null);

  // Poll dashboard every 3s
  useEffect(() => {
    const poll = async () => {
      try {
        const data = await api.getDriverDashboard(ambulanceId);
        setDashboard(data);
        // Flash alert when dispatched
        if (prevStatusRef.current !== 'dispatched' && data.status === 'dispatched') {
          setFlashAlert(true);
          setTimeout(() => setFlashAlert(false), 3000);
        }
        prevStatusRef.current = data.status;
      } catch {}
    };
    poll();
    pollingRef.current = setInterval(poll, 3000);
    return () => { if (pollingRef.current) clearInterval(pollingRef.current); };
  }, [ambulanceId]);

  // Poll routing when condition submitted
  useEffect(() => {
    if (!conditionSubmitted || !dashboard?.emergency_id) return;
    const poll = async () => {
      try {
        const r = await api.getRoutingStatus(dashboard.emergency_id!);
        setRouting(r);
        if (r.routing_status === 'routing_complete') {
          if (routingRef.current) clearInterval(routingRef.current);
        }
      } catch {}
    };
    poll();
    routingRef.current = setInterval(poll, 2000);
    return () => { if (routingRef.current) clearInterval(routingRef.current); };
  }, [conditionSubmitted, dashboard?.emergency_id]);

  const submitCondition = async () => {
    if (!dashboard?.emergency_id || !conditionForm.symptoms) return;
    setConditionLoading(true);
    try {
      await api.submitCondition(dashboard.emergency_id, conditionForm);
      setConditionSubmitted(true);
    } catch {}
    setConditionLoading(false);
  };

  const completeEmergency = async () => {
    try { await api.completeEmergency(ambulanceId); setIsComplete(true); } catch {}
  };

  const startSim = async () => {
    if (!dashboard?.emergency_id) return;
    setSimLoading(true);
    try {
      await api.startSimulation(dashboard.emergency_id, ambulanceId, 2);
      setSimRunning(true);
      // Poll simulation status every 1s
      simRef.current = setInterval(async () => {
        try {
          const s = await api.getSimulationStatus(dashboard.emergency_id!);
          setSimStatus(s);
          if (s.phase === 'complete' || s.phase === 'arrived') {
            clearInterval(simRef.current!);
            setSimRunning(false);
          }
        } catch {}
      }, 1000);
    } catch {}
    setSimLoading(false);
  };

  // Cleanup sim on unmount
  useEffect(() => () => { if (simRef.current) clearInterval(simRef.current); }, []);

  const routingLabel = (status: string, name?: string) => {
    if (status === 'checking_hospitals') return '🔍 Checking hospitals...';
    if (status?.startsWith('calling_')) return `📞 Calling ${name || status.replace('calling_', '')}...`;
    if (status === 'hospital_confirmed') return `✅ Hospital confirmed`;
    if (status === 'routing_complete') return `✅ Routing complete`;
    return `⏳ ${status}`;
  };

  const p = dashboard?.patient;

  return (
    <div className={`flex min-h-screen ${flashAlert ? 'flash-red' : ''}`} style={{ background: '#F0FDF9' }}>
      {/* ── Sidebar ─── */}
      <aside className="kairos-sidebar hidden md:flex">
        <div className="kairos-sidebar-logo">
          <div className="kairos-sidebar-logo-icon">K</div>
          <span className="font-bold text-white text-base">KAIROS</span>
        </div>
        <nav className="flex-1 py-4">
          {NAV_ITEMS.map(item => (
            <button key={item.id} onClick={() => setActiveNav(item.id)}
              className={`kairos-nav-item w-full text-left ${activeNav === item.id ? 'active' : ''}`}>
              <span>{item.icon}</span>
              <span>{item.label}</span>
            </button>
          ))}
        </nav>
        <div className="p-4 border-t border-white border-opacity-10">
          <p className="text-xs text-gray-500">Ambulance ID</p>
          <p className="text-white font-bold">{ambulanceId}</p>
          <div className="flex items-center gap-2 mt-2">
            <div className="w-2 h-2 rounded-full" style={{ background: dashboard?.status === 'dispatched' ? '#F59E0B' : '#16A34A' }}></div>
            <span className="text-xs font-semibold" style={{ color: dashboard?.status === 'dispatched' ? '#F59E0B' : '#16A34A' }}>
              {dashboard?.status === 'dispatched' ? 'On Dispatch' : 'On Duty'}
            </span>
          </div>
        </div>
      </aside>

      {/* ── Main Content ─── */}
      <main className="flex-1 p-6 overflow-auto">
        {/* Top bar */}
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-4">
            <div>
              <p className="text-xs text-gray-500 font-medium">Ambulance ID: <strong className="text-gray-800">{ambulanceId}</strong></p>
              <div className="flex items-center gap-2 mt-1">
                <div className="w-2 h-2 rounded-full" style={{ background: '#16A34A' }}></div>
                <span className="text-xs font-semibold" style={{ color: '#16A34A' }}>On Duty</span>
              </div>
            </div>
          </div>
          <button className="flex items-center gap-2 px-4 py-2 rounded-xl font-bold text-white text-sm" style={{ background: '#DC2626', minHeight: '44px' }}>
            📞 Emergency Call
          </button>
        </div>

        {/* ── Available State ─── */}
        {dashboard?.status === 'available' && (
          <div className="flex flex-col items-center justify-center h-64">
            <div className="text-6xl mb-4">🚑</div>
            <h2 className="text-xl font-bold text-gray-800 mb-2">Ready for Dispatch</h2>
            <p className="text-gray-500 text-sm">Waiting for emergency assignment...</p>
            <div className="flex items-center gap-2 mt-4">
              <div className="w-3 h-3 rounded-full" style={{ background: '#16A34A', animation: 'pulse 1.5s ease-in-out infinite' }}></div>
              <span className="text-sm font-medium text-gray-600">Standby</span>
            </div>
          </div>
        )}

        {/* ── Dispatched State ─── */}
        {(dashboard?.status === 'dispatched' || dashboard?.status === 'busy') && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Patient Info */}
            <div className="kairos-card">
              <h2 className="font-bold text-gray-800 mb-4" style={{ fontSize: '15px' }}>Patient Information</h2>
              {p ? (
                <>
                  <div className="flex items-center gap-3 mb-4">
                    <div className="w-12 h-12 rounded-full flex items-center justify-center font-bold text-white" style={{ background: '#2DD4BF' }}>
                      {p.name.split(' ').map(n => n[0]).join('').slice(0,2)}
                    </div>
                    <div>
                      <p className="font-bold text-gray-900">{p.name}</p>
                      <p className="text-sm text-gray-500">{p.age} Years · {p.blood_group}</p>
                    </div>
                  </div>
                  <div className="space-y-2 text-sm">
                    <div className="flex justify-between"><span className="text-gray-500">Blood</span><span className="kairos-badge kairos-badge-teal">{p.blood_group}</span></div>
                    <div className="flex justify-between"><span className="text-gray-500">Allergies</span><span className="font-medium">{p.allergies || 'None'}</span></div>
                    <div className="flex justify-between"><span className="text-gray-500">Emergency Contact</span>
                      <a href={`tel:${p.emergency_contact_phone}`} className="font-medium" style={{ color: '#2DD4BF' }}>📞 +91 {p.emergency_contact_phone}</a>
                    </div>
                  </div>
                </>
              ) : (
                <div className="p-3 rounded-xl" style={{ background: '#FEF3C7' }}>
                  <p className="text-sm font-semibold text-amber-800">⚠️ Unidentified Patient</p>
                  {dashboard?.unidentified_notes && <p className="text-xs text-amber-700 mt-1">{dashboard.unidentified_notes}</p>}
                </div>
              )}
            </div>

            {/* Map + Simulation Panel */}
            <div className="kairos-card">
              <div className="flex items-center justify-between mb-3">
                <h2 className="font-bold text-gray-800" style={{ fontSize: '15px' }}>Live Location</h2>
                {!simRunning && dashboard?.emergency_id && (
                  <button
                    onClick={startSim}
                    disabled={simLoading}
                    className="px-3 py-1 rounded-full text-xs font-bold text-white"
                    style={{ background: simLoading ? '#94A3B8' : '#2DD4BF' }}
                  >
                    {simLoading ? 'Starting...' : '▶ Start Simulation'}
                  </button>
                )}
                {simRunning && (
                  <span className="px-3 py-1 rounded-full text-xs font-bold text-white" style={{ background: '#F59E0B' }}>🔴 LIVE</span>
                )}
              </div>

              {/* Map area — shows live coords when simulation running */}
              <div className="map-container flex items-center justify-center mb-4" style={{ background: '#0F172A', height: '200px', borderRadius: '12px', position: 'relative' }}>
                {simStatus ? (
                  <div className="text-center">
                    <div className="text-3xl mb-2">🚑</div>
                    <p className="text-sm font-semibold" style={{ color: '#2DD4BF' }}>{simStatus.status_text || 'En route...'}</p>
                    <p className="text-xs text-gray-400 mt-1">
                      {simStatus.ambulance?.lat?.toFixed(4)}, {simStatus.ambulance?.lng?.toFixed(4)}
                    </p>
                    {/* Progress bar */}
                    {simStatus.progress_percent !== undefined && (
                      <div className="mt-3 w-48 h-1.5 rounded-full" style={{ background: '#1E293B' }}>
                        <div
                          className="h-1.5 rounded-full transition-all"
                          style={{ width: `${simStatus.progress_percent}%`, background: '#2DD4BF' }}
                        />
                      </div>
                    )}
                    <p className="text-xs text-gray-500 mt-1">{simStatus.progress_percent ?? 0}% complete</p>
                  </div>
                ) : (
                  <div className="text-center">
                    <div className="text-4xl mb-2">🗺️</div>
                    <p className="text-sm text-gray-400">Click "Start Simulation" to see live movement</p>
                    {dashboard?.pickup_lat && (
                      <p className="text-xs text-gray-600 mt-1">Patient @ {dashboard.pickup_lat?.toFixed(4)}, {dashboard.pickup_lng?.toFixed(4)}</p>
                    )}
                  </div>
                )}
              </div>

              {/* Sim phase badge */}
              {simStatus && (
                <div className="flex items-center gap-2 mb-3">
                  <div className="w-2 h-2 rounded-full" style={{ background: '#F59E0B' }}></div>
                  <p className="text-xs font-medium text-gray-600">
                    Phase: {simStatus.phase === 'en_route_to_patient' ? '🚑 → Patient' : simStatus.phase === 'en_route_to_hospital' ? '🚑 → Hospital' : simStatus.phase}
                  </p>
                </div>
              )}

              {dashboard?.pickup_directions_link && (
                <a href={dashboard.pickup_directions_link} target="_blank" rel="noopener noreferrer"
                  className="kairos-btn-primary w-full justify-center" style={{ borderRadius: '12px' }}>
                  🧭 Navigate to Patient
                </a>
              )}
            </div>

            {/* Right column */}
            <div className="space-y-4">
              {/* Prep Instructions */}
              {dashboard?.prep_instructions && dashboard.prep_instructions.length > 0 && (
                <div className="kairos-card">
                  <h3 className="font-bold text-gray-800 mb-3" style={{ fontSize: '15px' }}>AI Pre-Arrival Prep</h3>
                  <div className="space-y-2">
                    {dashboard.prep_instructions.map((item, i) => (
                      <div key={i} className="flex items-center gap-2 text-sm">
                        <div className="w-5 h-5 rounded-full flex items-center justify-center flex-shrink-0" style={{ background: '#DCFCE7' }}>
                          <span style={{ color: '#16A34A', fontSize: '10px' }}>✓</span>
                        </div>
                        <span className="text-gray-700">{item}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Hospital Routing */}
              {dashboard?.hospital_name && (
                <div className="kairos-card">
                  <h3 className="font-bold text-gray-800 mb-3" style={{ fontSize: '15px' }}>✅ Hospital Confirmed</h3>
                  <p className="font-bold text-gray-900 mb-1">{dashboard.hospital_name}</p>
                  {dashboard.hospital_address && <p className="text-xs text-gray-500 mb-3">{dashboard.hospital_address}</p>}
                  {dashboard.scoring_reason && <p className="text-xs text-gray-500 mb-3 italic">"{dashboard.scoring_reason}"</p>}
                  <p className="text-xs font-medium mb-3" style={{ color: '#2DD4BF' }}>Hospital ER has been briefed ✓</p>
                  {dashboard.hospital_directions_link && (
                    <a href={dashboard.hospital_directions_link} target="_blank" rel="noopener noreferrer" className="kairos-btn-primary w-full justify-center" style={{ fontSize: '13px' }}>
                      🏥 Navigate to {dashboard.hospital_name}
                    </a>
                  )}
                </div>
              )}

              {/* Routing status panel */}
              {conditionSubmitted && routing && !dashboard?.hospital_name && (
                <div className="kairos-card">
                  <h3 className="font-bold text-gray-800 mb-3" style={{ fontSize: '15px' }}>🔍 AI Hospital Routing</h3>
                  <div className="space-y-2">
                    {routing.hospitals_checked.map((h, i) => (
                      <div key={i} className="routing-row text-sm">
                        <span className="text-gray-700">{h.name}</span>
                        <span className={`kairos-badge ${h.status === 'available' ? 'kairos-badge-green' : 'kairos-badge-red'}`}>
                          {h.status === 'available' ? '✅ Available' : '❌ Unavailable'}
                        </span>
                      </div>
                    ))}
                    {routing.routing_status !== 'routing_complete' && (
                      <div className="flex items-center gap-2 pt-2">
                        <div className="spinner" style={{ width: '16px', height: '16px' }}></div>
                        <p className="text-xs text-gray-500">{routingLabel(routing.routing_status)}</p>
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {/* ── Condition Form (shows when dispatched and no hospital yet) ─── */}
        {dashboard?.status === 'dispatched' && !conditionSubmitted && dashboard.emergency_id && (
          <div className="mt-6 kairos-card max-w-2xl">
            <h2 className="font-bold text-gray-800 mb-4">Patient Condition Update</h2>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
              <div>
                <label className="kairos-label">BP</label>
                <input className="kairos-input" placeholder="90/60" value={conditionForm.vitals} onChange={e => setConditionForm(f => ({ ...f, vitals: e.target.value }))} />
              </div>
              <div>
                <label className="kairos-label">Consciousness</label>
                <select className="kairos-input" value={conditionForm.consciousness_level} onChange={e => setConditionForm(f => ({ ...f, consciousness_level: e.target.value }))}>
                  <option value="">Select...</option>
                  <option>Conscious</option><option>Semi-conscious</option><option>Unconscious</option>
                </select>
              </div>
              <div>
                <label className="kairos-label">Visible Injuries</label>
                <input className="kairos-input" placeholder="Head trauma..." value={conditionForm.visible_injuries} onChange={e => setConditionForm(f => ({ ...f, visible_injuries: e.target.value }))} />
              </div>
            </div>
            <div className="mb-4">
              <label className="kairos-label">Symptoms *</label>
              <textarea className="kairos-input" placeholder="Describe symptoms..." value={conditionForm.symptoms} onChange={e => setConditionForm(f => ({ ...f, symptoms: e.target.value }))} style={{ minHeight: '80px' }} />
            </div>
            <button onClick={submitCondition} disabled={!conditionForm.symptoms || conditionLoading} className="kairos-btn-primary" style={{ opacity: !conditionForm.symptoms ? 0.5 : 1 }}>
              {conditionLoading ? 'Submitting...' : '🔍 Submit Condition & Find Hospital'}
            </button>
          </div>
        )}

        {/* Complete emergency */}
        {dashboard?.hospital_name && !isComplete && (
          <div className="mt-4 max-w-2xl">
            <button onClick={completeEmergency} className="kairos-btn-secondary">✓ Mark Patient Delivered</button>
          </div>
        )}
        {isComplete && (
          <div className="mt-4 kairos-card max-w-2xl text-center">
            <p className="text-2xl mb-1">✅</p>
            <p className="font-bold text-gray-800">Emergency Complete — Ambulance is now available</p>
          </div>
        )}
      </main>
    </div>
  );
}
