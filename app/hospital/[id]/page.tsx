'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import { useParams } from 'next/navigation';
import api from '@/lib/apiClient';

interface PatientCard { name: string; age: number; blood_group: string; conditions?: string; allergies?: string; medications?: string; emergency_contact_name: string; emergency_contact_phone: string; }
interface HospitalStatus { emergency?: { id: string; patient?: PatientCard; unidentified_notes?: string; triage_result?: any; live_condition?: any; ambulance_eta_minutes?: number; ambulance_status?: string; scoring_reason?: string; }; new_patient_alert: boolean; }

const NAV_ITEMS = [
  { label: 'ER Dashboard', icon: '⊞', id: 'dashboard' },
  { label: 'Incoming Patients', icon: '🏃', id: 'incoming' },
  { label: 'Patient List', icon: '📋', id: 'list' },
  { label: 'Bed Management', icon: '🛏️', id: 'beds' },
  { label: 'Alerts', icon: '🔔', id: 'alerts' },
  { label: 'History', icon: '📁', id: 'history' },
];

const STATUS_STEPS = ['Dispatched', 'En Route', '5 Minutes Away', 'Arrived'];

export default function HospitalDashboard() {
  const { id } = useParams<{ id: string }>();
  const hospitalId = id || 'hospital-1';

  const [status, setStatus] = useState<HospitalStatus | null>(null);
  const [ambulanceLoc, setAmbulanceLoc] = useState<{ lat: number; lng: number; eta_minutes: number } | null>(null);
  const [bedStatus, setBedStatus] = useState<'idle' | 'confirmed' | 'unavailable'>('idle');
  const [acknowledged, setAcknowledged] = useState(false);
  const [activeNav, setActiveNav] = useState('dashboard');
  const [alertFired, setAlertFired] = useState(false);
  const [smsBanner, setSmsBanner] = useState(false);
  const pollingRef = useRef<NodeJS.Timeout | null>(null);
  const ambulanceRef = useRef<NodeJS.Timeout | null>(null);
  const audioRef = useRef<AudioContext | null>(null);
  const smsTimerRef = useRef<NodeJS.Timeout | null>(null);
  const prevAlertRef = useRef(false);

  const playAlert = useCallback(() => {
    try {
      if (!audioRef.current) audioRef.current = new AudioContext();
      const ctx = audioRef.current;
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.frequency.value = 880;
      osc.type = 'square';
      gain.gain.value = 0.3;
      osc.start();
      osc.stop(ctx.currentTime + 0.8);
      setTimeout(() => {
        const osc2 = ctx.createOscillator();
        const gain2 = ctx.createGain();
        osc2.connect(gain2);
        gain2.connect(ctx.destination);
        osc2.frequency.value = 660;
        osc2.type = 'square';
        gain2.gain.value = 0.3;
        osc2.start(ctx.currentTime);
        osc2.stop(ctx.currentTime + 0.8);
      }, 900);
    } catch {}
  }, []);

  const fireAlert = useCallback((emergency: HospitalStatus['emergency']) => {
    if (!emergency || alertFired) return;
    setAlertFired(true);
    // Flash screen
    document.body.classList.add('flash-red');
    setTimeout(() => document.body.classList.remove('flash-red'), 1500);
    // Play audio
    playAlert();
    // Push notification
    if ('Notification' in window && Notification.permission === 'granted') {
      new Notification('Incoming Patient — Kairos AI', {
        body: `Patient: ${emergency.patient?.name || 'Unidentified'} | ETA: ${Math.round(emergency.ambulance_eta_minutes || 0)} min`,
        icon: '/icons/icon-192x192.png',
      });
    }
    // SMS timer — 2 minutes
    smsTimerRef.current = setTimeout(() => {
      if (!acknowledged) setSmsBanner(true);
    }, 120000);
  }, [alertFired, acknowledged, playAlert]);

  // Request notification permission on load
  useEffect(() => {
    if ('Notification' in window && Notification.permission === 'default') {
      Notification.requestPermission();
    }
  }, []);

  // Poll hospital status every 3s
  useEffect(() => {
    const poll = async () => {
      try {
        const data: HospitalStatus = await api.getHospitalStatus(hospitalId);
        setStatus(data);
        if (data.new_patient_alert && !prevAlertRef.current) {
          fireAlert(data.emergency);
        }
        prevAlertRef.current = data.new_patient_alert;
      } catch {}
    };
    poll();
    pollingRef.current = setInterval(poll, 3000);
    return () => {
      if (pollingRef.current) clearInterval(pollingRef.current);
      if (smsTimerRef.current) clearTimeout(smsTimerRef.current);
    };
  }, [hospitalId, fireAlert]);

  // Poll ambulance location every 5s
  useEffect(() => {
    if (!status?.emergency) return;
    const poll = async () => {
      try {
        const loc = await api.getHospitalAmbulanceLocation(hospitalId);
        setAmbulanceLoc(loc);
      } catch {}
    };
    poll();
    ambulanceRef.current = setInterval(poll, 5000);
    return () => { if (ambulanceRef.current) clearInterval(ambulanceRef.current); };
  }, [hospitalId, status?.emergency]);

  const handleAcknowledge = async () => {
    try {
      await api.acknowledgeAlert(hospitalId);
      setAcknowledged(true);
      setSmsBanner(false);
      if (smsTimerRef.current) clearTimeout(smsTimerRef.current);
    } catch {}
  };

  const handleBed = async (s: 'confirmed' | 'unavailable') => {
    if (!status?.emergency) return;
    try {
      await api.confirmBed(hospitalId, status.emergency.id, s);
      setBedStatus(s);
    } catch {}
  };

  const emergency = status?.emergency;
  const patient = emergency?.patient;
  const eta = ambulanceLoc?.eta_minutes ?? emergency?.ambulance_eta_minutes;
  const triageResult = emergency?.triage_result;
  const liveCondition = emergency?.live_condition;

  // Determine status step
  const etaValue = eta ?? 999;
  const currentStep = etaValue < 1 ? 3 : etaValue <= 5 ? 2 : emergency ? 1 : 0;

  return (
    <div className="flex min-h-screen" style={{ background: '#F0FDF9' }}>
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
              <span>{item.icon}</span><span>{item.label}</span>
            </button>
          ))}
        </nav>
        <div className="p-4 border-t border-white border-opacity-10">
          <p className="text-xs text-gray-500">Hospital ID</p>
          <p className="text-white font-bold text-sm">{hospitalId}</p>
          <p className="text-xs text-gray-500 mt-1">Kairos Urgent Care</p>
        </div>
      </aside>

      {/* ── Main ─── */}
      <main className="flex-1 overflow-auto">
        {/* Alert Banner */}
        {emergency && !acknowledged && (
          <div className="px-6 pt-4">
            <div className="alert-banner">
              <div className="flex-1">
                <p className="font-bold text-red-800 text-base">Incoming Critical Patient</p>
                <p className="text-xs text-red-600 font-medium">Live emergency · auto-refreshing</p>
              </div>
              <div className="flex gap-6 text-sm">
                <div>
                  <p className="text-gray-500 text-xs uppercase">ETA</p>
                  <p className="font-bold text-red-700 text-lg">{eta ? `${Math.round(eta)} min` : '—'}</p>
                </div>
                <div>
                  <p className="text-gray-500 text-xs uppercase">Patient</p>
                  <p className="font-bold text-gray-900">{patient ? `${patient.name}, ${patient.age} M` : 'Unidentified'}</p>
                </div>
                <div>
                  <p className="text-gray-500 text-xs uppercase">Emergency</p>
                  <p className="font-bold" style={{ color: '#DC2626' }}>{triageResult?.emergency_type || 'Under assessment'}</p>
                </div>
              </div>
              <button onClick={handleAcknowledge} className="kairos-btn-primary ml-4 flex-shrink-0">Prepare for Arrival</button>
            </div>
          </div>
        )}

        {/* SMS Banner */}
        {smsBanner && (
          <div className="px-6 pt-2">
            <div className="rounded-xl p-3 flex items-center gap-2" style={{ background: '#FEF3C7' }}>
              <span>📱</span>
              <p className="text-sm text-amber-800 font-medium">SMS sent to charge nurse — alert unacknowledged for 2 minutes</p>
              <button onClick={() => setSmsBanner(false)} className="ml-auto text-amber-600 text-xs">Dismiss</button>
            </div>
          </div>
        )}

        <div className="p-6">
          {/* No emergency */}
          {!emergency && (
            <div className="flex flex-col items-center justify-center h-64">
              <div className="text-5xl mb-4">🏥</div>
              <h2 className="text-xl font-bold text-gray-800 mb-2">ER Ready</h2>
              <p className="text-gray-500 text-sm">Monitoring for incoming patients...</p>
              <div className="flex items-center gap-2 mt-4">
                <div className="spinner" style={{ width: '16px', height: '16px' }}></div>
                <span className="text-sm text-gray-500">Auto-refreshing every 3 seconds</span>
              </div>
            </div>
          )}

          {emergency && (
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              {/* Patient Medical Card */}
              <div className="kairos-card">
                <h2 className="font-bold text-gray-800 mb-4">Patient Medical Card</h2>
                {patient ? (
                  <>
                    <div className="space-y-3 text-sm">
                      <div className="medical-info-row">
                        <span className="medical-info-label">Blood Group</span>
                        <span className="kairos-badge kairos-badge-teal">{patient.blood_group}</span>
                      </div>
                      <div className="medical-info-row">
                        <span className="medical-info-label">Allergies</span>
                        <span className="medical-info-value">{patient.allergies || 'None'}</span>
                      </div>
                      <div className="medical-info-row">
                        <span className="medical-info-label">Medical Conditions</span>
                        <span className="medical-info-value">{patient.conditions || 'No major conditions'}</span>
                      </div>
                      <div className="medical-info-row">
                        <span className="medical-info-label">Medications</span>
                        <span className="medical-info-value" style={{ color: '#2DD4BF' }}>{patient.medications || 'Not Available'}</span>
                      </div>
                      <div className="medical-info-row">
                        <span className="medical-info-label">Emergency Contact</span>
                        <a href={`tel:${patient.emergency_contact_phone}`} className="text-sm font-semibold" style={{ color: '#2DD4BF' }}>
                          +91 {patient.emergency_contact_phone}
                        </a>
                      </div>
                    </div>
                    <button className="kairos-btn-secondary w-full justify-center mt-4 text-sm">View Full Medical Profile</button>
                  </>
                ) : (
                  <div>
                    <div className="p-3 rounded-xl mb-4 flex items-center gap-2" style={{ background: '#FEE2E2' }}>
                      <span>⚠️</span>
                      <p className="text-sm font-bold text-red-700">Unidentified Patient — Verify on Arrival</p>
                    </div>
                    {emergency.unidentified_notes && (
                      <p className="text-sm text-gray-600">{emergency.unidentified_notes}</p>
                    )}
                  </div>
                )}

                {/* Triage */}
                {triageResult && (
                  <div className="mt-4 pt-4 border-t border-gray-100">
                    <p className="text-xs font-bold text-gray-500 uppercase tracking-wider mb-2">AI Triage Summary</p>
                    <div className="flex flex-wrap gap-2">
                      {triageResult.emergency_type && <span className="kairos-badge kairos-badge-red">{triageResult.emergency_type}</span>}
                      {triageResult.bed_type_needed && <span className="kairos-badge kairos-badge-amber">{triageResult.bed_type_needed} Required</span>}
                      {triageResult.specialist_needed && <span className="kairos-badge kairos-badge-teal">{triageResult.specialist_needed}</span>}
                    </div>
                  </div>
                )}
              </div>

              {/* Live Tracking */}
              <div className="kairos-card">
                <h2 className="font-bold text-gray-800 mb-4">Live Tracking</h2>
                <div className="map-container flex items-center justify-center mb-4" style={{ background: '#E8F5F3', height: '220px' }}>
                  <div className="text-center">
                    <div className="text-4xl mb-2">🚑</div>
                    <p className="text-sm text-gray-500">Ambulance en route</p>
                    {ambulanceLoc && (
                      <p className="text-xs text-gray-400 mt-1">{ambulanceLoc.lat.toFixed(4)}, {ambulanceLoc.lng.toFixed(4)}</p>
                    )}
                  </div>
                </div>

                {/* Stats row */}
                <div className="grid grid-cols-3 gap-3 mb-4 text-center">
                  <div>
                    <p className="text-xs text-gray-500">Distance</p>
                    <p className="font-bold text-gray-900">2.4 km</p>
                  </div>
                  <div>
                    <p className="text-xs text-gray-500">ETA</p>
                    <p className="font-bold" style={{ color: '#2DD4BF' }}>{eta ? `${Math.round(eta)} min` : '—'}</p>
                  </div>
                  <div>
                    <p className="text-xs text-gray-500">Route</p>
                    <p className="font-bold text-gray-900 text-xs">NH 48</p>
                  </div>
                </div>

                <button className="kairos-btn-secondary w-full justify-center text-sm">
                  🗺️ Open in Maps
                </button>

                {/* Status bar */}
                <div className="flex items-center justify-between mt-4">
                  {STATUS_STEPS.map((s, i) => (
                    <div key={i} className="flex flex-col items-center gap-1">
                      <div className="w-6 h-6 rounded-full flex items-center justify-center" style={{
                        background: i === currentStep ? '#2DD4BF' : i < currentStep ? '#DCFCE7' : '#E2E8F0'
                      }}>
                        {i < currentStep ? <span style={{ fontSize: '10px', color: '#16A34A' }}>✓</span> : null}
                      </div>
                      <p className="text-xs text-center" style={{ color: i === currentStep ? '#2DD4BF' : '#94A3B8', maxWidth: '50px' }}>{s}</p>
                    </div>
                  ))}
                </div>
              </div>

              {/* Right column */}
              <div className="space-y-4">
                {/* ER Prep Checklist */}
                <div className="kairos-card">
                  <h3 className="font-bold text-gray-800 mb-3">ER Preparation Checklist</h3>
                  {[
                    'ICU Bed Reserved',
                    triageResult?.emergency_type === 'cardiac' ? 'Cardiac Team Alerted' : 'ER Team Alerted',
                    'Ventilator Ready',
                    'Emergency Blood Reserved',
                    'OT Standby',
                  ].map((item, i) => (
                    <div key={i} className="flex items-center gap-2 py-2 border-b border-gray-50 last:border-0">
                      <div className="w-5 h-5 rounded-full flex items-center justify-center flex-shrink-0" style={{ background: i < 4 ? '#DCFCE7' : '#F1F5F9' }}>
                        {i < 4 ? <span style={{ color: '#16A34A', fontSize: '10px' }}>✓</span> : <span style={{ color: '#94A3B8', fontSize: '10px' }}>○</span>}
                      </div>
                      <span className="text-sm" style={{ color: i < 4 ? '#16A34A' : '#64748B' }}>{item}</span>
                    </div>
                  ))}
                </div>

                {/* Live updates */}
                {liveCondition && (
                  <div className="kairos-card">
                    <h3 className="font-bold text-gray-800 mb-3">Live Updates from Ambulance</h3>
                    <div className="space-y-2">
                      {liveCondition.symptoms && (
                        <div className="flex gap-2 text-sm">
                          <div className="w-2 h-2 rounded-full mt-1.5 flex-shrink-0" style={{ background: '#2DD4BF' }}></div>
                          <p className="text-gray-600">{liveCondition.symptoms}</p>
                        </div>
                      )}
                      {liveCondition.vitals && (
                        <div className="flex gap-2 text-sm">
                          <div className="w-2 h-2 rounded-full mt-1.5 flex-shrink-0" style={{ background: '#2DD4BF' }}></div>
                          <p className="text-gray-600">Vitals: {liveCondition.vitals}</p>
                        </div>
                      )}
                      {liveCondition.consciousness_level && (
                        <div className="flex gap-2 text-sm">
                          <div className="w-2 h-2 rounded-full mt-1.5 flex-shrink-0" style={{ background: '#F59E0B' }}></div>
                          <p className="text-gray-600">Consciousness: {liveCondition.consciousness_level}</p>
                        </div>
                      )}
                    </div>
                  </div>
                )}

                {/* Bed confirmation */}
                <div className="kairos-card">
                  <h3 className="font-bold text-gray-800 mb-4">Bed Status</h3>
                  {bedStatus === 'idle' && (
                    <div className="space-y-3">
                      <button onClick={() => handleBed('confirmed')} className="kairos-btn-primary w-full justify-center" style={{ background: '#16A34A' }}>
                        ✅ Confirm Bed Ready
                      </button>
                      <button onClick={() => handleBed('unavailable')} className="kairos-btn-danger w-full justify-center">
                        ❌ Bed Unavailable
                      </button>
                    </div>
                  )}
                  {bedStatus === 'confirmed' && (
                    <div className="text-center p-3 rounded-xl" style={{ background: '#DCFCE7' }}>
                      <p className="text-2xl mb-1">✅</p>
                      <p className="font-bold" style={{ color: '#16A34A' }}>Bed Confirmed</p>
                    </div>
                  )}
                  {bedStatus === 'unavailable' && (
                    <div className="text-center p-3 rounded-xl" style={{ background: '#FEF3C7' }}>
                      <p className="text-sm font-semibold text-amber-800 mb-1">AI is re-routing ambulance to next available hospital...</p>
                      <div className="flex items-center justify-center gap-2">
                        <div className="spinner" style={{ width: '16px', height: '16px' }}></div>
                        <span className="text-xs text-amber-600">Finding alternative</span>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
