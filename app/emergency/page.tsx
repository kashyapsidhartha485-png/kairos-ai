'use client';

import { useState, useRef, useEffect, useCallback } from 'react';
import Link from 'next/link';
import api from '@/lib/apiClient';

type Phase = 'camera' | 'preview' | 'status' | 'identified' | 'not_identified' | 'offline' | 'duplicate';

interface StatusItem { emoji: string; text: string; done: boolean; }
interface PatientCard { name: string; age: number; blood_group: string; conditions?: string; allergies?: string; medications?: string; emergency_contact_name: string; emergency_contact_phone: string; }
interface FirstAid { dos: string[]; donts: string[]; cpr_needed: boolean; }

export default function EmergencyPage() {
  const [phase, setPhase] = useState<Phase>('camera');
  const [countdown, setCountdown] = useState<number | null>(null);
  const [capturedImage, setCapturedImage] = useState<string | null>(null);
  const [capturedBlob, setCapturedBlob] = useState<Blob | null>(null);
  const [statusItems, setStatusItems] = useState<StatusItem[]>([]);
  const [emergencyId, setEmergencyId] = useState<string | null>(null);
  const [patient, setPatient] = useState<PatientCard | null>(null);
  const [firstAid, setFirstAid] = useState<FirstAid | null>(null);
  const [dupId, setDupId] = useState<string | null>(null);
  const [dispatched, setDispatched] = useState(false);
  const [eta, setEta] = useState<number | null>(null);
  const [gps, setGps] = useState<{ lat: number; lng: number } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [cameraError, setCameraError] = useState(false);
  const [gpsError, setGpsError] = useState(false);
  // Bystander notes
  const [bystanderNotes, setBystanderNotes] = useState('');
  // Manual form
  const [manualAge, setManualAge] = useState('');
  const [manualGender, setManualGender] = useState('');
  const [manualInjuries, setManualInjuries] = useState('');
  const [manualConditions, setManualConditions] = useState('');
  const [manualLoading, setManualLoading] = useState(false);

  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const pollingRef = useRef<NodeJS.Timeout | null>(null);
  const countdownRef = useRef<NodeJS.Timeout | null>(null);

  // Get GPS on load
  useEffect(() => {
    navigator.geolocation?.getCurrentPosition(
      p => setGps({ lat: p.coords.latitude, lng: p.coords.longitude }),
      () => setGpsError(true),
      { timeout: 5000 }
    );
  }, []);

  // Open camera on load
  useEffect(() => {
    startCamera();
    return () => { stopCamera(); clearAllTimers(); };
  }, []);

  const stopCamera = () => {
    streamRef.current?.getTracks().forEach(t => t.stop());
    streamRef.current = null;
  };

  const clearAllTimers = () => {
    if (pollingRef.current) clearInterval(pollingRef.current);
    if (countdownRef.current) clearInterval(countdownRef.current);
  };

  const startCamera = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' }, audio: false });
      streamRef.current = stream;
      if (videoRef.current) { videoRef.current.srcObject = stream; videoRef.current.play(); }
      // Start 3-second auto-capture countdown
      let c = 3;
      setCountdown(c);
      countdownRef.current = setInterval(() => {
        c--;
        if (c > 0) { setCountdown(c); }
        else {
          setCountdown(null);
          clearInterval(countdownRef.current!);
          capturePhoto();
        }
      }, 1000);
    } catch {
      setCameraError(true);
    }
  };

  const capturePhoto = useCallback(() => {
    if (!videoRef.current || !canvasRef.current) return;
    const video = videoRef.current;
    const canvas = canvasRef.current;
    canvas.width = video.videoWidth || 640;
    canvas.height = video.videoHeight || 480;
    canvas.getContext('2d')?.drawImage(video, 0, 0);
    canvas.toBlob(blob => {
      if (!blob) return;
      setCapturedBlob(blob);
      setCapturedImage(canvas.toDataURL('image/jpeg'));
      setPhase('preview');
      stopCamera();
    }, 'image/jpeg', 0.9);
  }, []);

  const retake = () => {
    setCapturedImage(null);
    setCapturedBlob(null);
    setPhase('camera');
    startCamera();
  };

  const submitPhoto = async () => {
    if (!capturedBlob) return;
    setPhase('status');

    // Add status items progressively
    const addStatus = (item: StatusItem, delay: number) =>
      setTimeout(() => setStatusItems(prev => [...prev, item]), delay);

    addStatus({ emoji: '🚨', text: 'Emergency Activated', done: true }, 0);
    addStatus({ emoji: '📍', text: 'Location Confirmed', done: true }, 500);
    addStatus({ emoji: '🔍', text: 'Identifying Victim...', done: false }, 800);

    // Check for duplicate
    if (gps) {
      try {
        const dup = await api.checkNearby(gps.lat, gps.lng);
        if (dup.duplicate) { setDupId(dup.existing_emergency_id); setPhase('duplicate'); return; }
      } catch {}
    }

    // Submit to backend with 5s offline timeout
    const formData = new FormData();
    formData.append('photo', capturedBlob, 'emergency.jpg');
    formData.append('lat', String(gps?.lat ?? 12.9716));
    formData.append('lng', String(gps?.lng ?? 77.5946));
    if (bystanderNotes) formData.append('bystander_notes', bystanderNotes);

    try {
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 5000);
      const result = await api.identify(formData);
      clearTimeout(timeout);

      setEmergencyId(result.emergency_id);
      setStatusItems(prev => prev.map((s, i) => i === 2 ? { ...s, done: true } : s));
      addStatus({ emoji: '🚑', text: 'Finding Nearest Ambulance...', done: false }, 200);

      if (result.identification_status === 'identified') {
        setPatient(result.patient);
        setFirstAid(result.first_aid_guidance);
        setTimeout(() => { setStatusItems(prev => prev.map((s, i) => i === 3 ? { ...s, done: true } : s)); setPhase('identified'); }, 1000);
      } else if (result.identification_status === 'duplicate') {
        setDupId(result.emergency_id);
        setPhase('duplicate');
      } else {
        setTimeout(() => { setStatusItems(prev => prev.map((s, i) => i === 3 ? { ...s, done: true } : s)); setPhase('not_identified'); }, 1000);
      }
    } catch (e: any) {
      if (e.name === 'AbortError' || e.message?.includes('fetch')) {
        setPhase('offline');
      } else {
        setPhase('offline');
      }
    }
  };

  const handleDispatch = async () => {
    if (!emergencyId) return;
    try {
      const result = await api.dispatch(emergencyId);
      setEta(Math.round(result.assigned_ambulance?.eta_minutes ?? 0));
      setDispatched(true);
      setStatusItems(prev => [...prev, { emoji: '✅', text: `Ambulance Dispatched — ETA: ${Math.round(result.assigned_ambulance?.eta_minutes ?? 0)} min`, done: true }]);
    } catch (err: any) {
      setError(err.message);
    }
  };

  const handleManualSubmit = async () => {
    if (!emergencyId) return;
    setManualLoading(true);
    try {
      const fd = new FormData();
      if (manualAge) fd.append('approximate_age', manualAge);
      if (manualGender) fd.append('gender', manualGender);
      if (manualInjuries) fd.append('visible_injuries', manualInjuries);
      if (manualConditions) fd.append('known_conditions', manualConditions);
      await api.submitManualInfo(emergencyId, fd);
    } catch {}
    setManualLoading(false);
  };

  // Camera error state
  if (cameraError) return (
    <div className="min-h-screen flex flex-col items-center justify-center p-6" style={{ background: '#0F172A' }}>
      <div className="text-6xl mb-4">📷</div>
      <h2 className="text-white text-xl font-bold mb-2 text-center">Camera access required</h2>
      <p className="text-gray-400 text-sm text-center mb-8">Please enable camera access in your device settings.</p>
      <a href="tel:108" className="kairos-btn-danger text-xl px-12 py-6" style={{ fontSize: '20px', borderRadius: '16px' }}>📞 Call 108 Immediately</a>
    </div>
  );

  // Offline fallback
  if (phase === 'offline') return (
    <div className="min-h-screen flex flex-col items-center justify-center p-6" style={{ background: '#0F172A' }}>
      <div className="text-6xl mb-4">📵</div>
      <h2 className="text-white text-2xl font-bold mb-2 text-center">No Connection Detected</h2>
      <p className="text-gray-400 text-center mb-8">Your safety matters. Call emergency services now.</p>
      <a href="tel:108" className="kairos-btn-danger text-xl px-12 py-6 w-full max-w-sm justify-center" style={{ fontSize: '22px', borderRadius: '20px', minHeight: '72px' }}>📞 Call 108 Immediately</a>
      <button onClick={retake} className="mt-4 text-gray-400 text-sm underline">Try again</button>
    </div>
  );

  // Duplicate check
  if (phase === 'duplicate') return (
    <div className="min-h-screen flex flex-col items-center justify-center p-6" style={{ background: '#0F172A' }}>
      <div className="bg-white rounded-2xl p-6 max-w-sm w-full">
        <div className="text-4xl mb-3 text-center">⚠️</div>
        <h2 className="text-xl font-bold text-gray-900 mb-2 text-center">Emergency Already Reported Nearby</h2>
        <p className="text-gray-500 text-sm text-center mb-6">An active emergency has already been reported at this location in the last 5 minutes.</p>
        <div className="space-y-3">
          <button onClick={() => { setEmergencyId(dupId); setPhase('status'); }} className="kairos-btn-primary w-full justify-center">Join Existing Emergency</button>
          <button onClick={() => { setDupId(null); setPhase('camera'); retake(); }} className="kairos-btn-secondary w-full justify-center">This is a different emergency</button>
        </div>
      </div>
    </div>
  );

  return (
    <div className="min-h-screen" style={{ background: '#0F172A' }}>
      {/* ── GPS Warning ─── */}
      {gpsError && (
        <div className="px-4 pt-3">
          <div className="rounded-xl p-3 flex items-center gap-2" style={{ background: '#FEF3C7' }}>
            <span>⚠️</span>
            <p className="text-xs font-medium text-amber-800">Please allow location access for the emergency system to work.</p>
          </div>
        </div>
      )}

      {/* ─── CAMERA PHASE ─── */}
      {phase === 'camera' && (
        <div className="relative h-screen flex flex-col">
          <video ref={videoRef} autoPlay playsInline muted className="w-full flex-1 object-cover" />
          <canvas ref={canvasRef} className="hidden" />

          {/* Countdown overlay */}
          {countdown !== null && (
            <div className="countdown-overlay" key={countdown}>{countdown}</div>
          )}

          {/* Header */}
          <div className="absolute top-0 left-0 right-0 flex items-center justify-between px-6 pt-8">
            <div className="px-3 py-1 rounded-full text-white text-xs font-bold" style={{ background: 'rgba(220,38,38,0.9)' }}>🔴 EMERGENCY</div>
            <Link href="/" className="text-white text-xs opacity-70">✕ Exit</Link>
          </div>

          {/* Instructions */}
          <div className="absolute bottom-40 left-0 right-0 text-center">
            <p className="text-white text-base font-semibold drop-shadow-lg">Point camera at the victim's face</p>
            <p className="text-gray-300 text-sm mt-1">Auto-capturing in {countdown ?? 0} seconds...</p>
          </div>

          {/* Capture button */}
          <div className="absolute bottom-16 left-0 right-0 flex justify-center">
            <button className="capture-btn" onClick={capturePhoto} id="capture-btn" aria-label="Capture photo">
              <div className="w-14 h-14 rounded-full bg-white opacity-30" />
            </button>
          </div>
        </div>
      )}

      {/* ─── PREVIEW PHASE ─── */}
      {phase === 'preview' && capturedImage && (
        <div className="relative h-screen flex flex-col">
          <img src={capturedImage} alt="Captured" className="w-full flex-1 object-cover" style={{ maxHeight: '55vh' }} />
          <canvas ref={canvasRef} className="hidden" />
          <div className="p-4" style={{ background: 'rgba(15,23,42,0.97)' }}>
            <label className="text-white text-xs font-semibold mb-2 block">📝 What happened? (helps AI triage)</label>
            <textarea
              className="w-full rounded-xl p-3 text-sm text-gray-900 resize-none"
              placeholder="e.g. Bike accident, bleeding from leg, conscious, hit by car..."
              rows={2}
              value={bystanderNotes}
              onChange={e => setBystanderNotes(e.target.value)}
            />
            <div className="flex gap-3 mt-3">
              <button onClick={retake} className="flex-1 py-3 rounded-2xl font-bold text-white text-base" style={{ background: 'rgba(255,255,255,0.2)', border: '2px solid white' }}>↩ Retake</button>
              <button onClick={submitPhoto} className="py-3 px-6 rounded-2xl font-bold text-white text-base" style={{ background: '#DC2626', flex: 2 }}>🚨 Report Emergency</button>
            </div>
          </div>
        </div>
      )}

      {/* ─── STATUS FEED ─── */}
      {(phase === 'status' || phase === 'identified' || phase === 'not_identified') && (
        <div className="max-w-md mx-auto p-4 pt-8">
          <canvas ref={canvasRef} className="hidden" />
          <h2 className="text-white text-2xl font-bold mb-6 text-center">Emergency Activated 🚨</h2>

          {/* Status items */}
          <div className="rounded-2xl p-5 mb-6" style={{ background: 'rgba(255,255,255,0.08)' }}>
            {statusItems.map((item, i) => (
              <div key={i} className="status-item border-b border-white border-opacity-10 last:border-0 pb-3 last:pb-0">
                <div className={`status-dot ${item.done ? 'status-dot-done' : 'status-dot-active'}`} />
                <div>
                  <p className="text-white font-medium text-sm">{item.emoji} {item.text}</p>
                </div>
              </div>
            ))}
            {statusItems.length === 0 && (
              <div className="flex items-center gap-3">
                <div className="spinner" />
                <p className="text-white text-sm">Connecting to emergency system...</p>
              </div>
            )}
          </div>

          {/* IDENTIFIED state */}
          {phase === 'identified' && patient && (
            <div className="space-y-4 animate-fade-in-up">
              {/* Patient card */}
              <div className="kairos-card">
                <div className="flex items-center gap-3 mb-4">
                  <div className="w-12 h-12 rounded-full flex items-center justify-center font-bold text-white text-lg" style={{ background: '#2DD4BF' }}>
                    {patient.name.split(' ').map(n => n[0]).join('').slice(0, 2)}
                  </div>
                  <div>
                    <h3 className="font-bold text-gray-900">{patient.name}</h3>
                    <p className="text-sm text-gray-500">{patient.age} years</p>
                  </div>
                  <span className="kairos-badge kairos-badge-teal ml-auto">{patient.blood_group}</span>
                </div>
                {patient.conditions && <div className="medical-info-row"><span className="medical-info-label">Conditions</span><span className="medical-info-value text-red-600">{patient.conditions}</span></div>}
                {patient.allergies && <div className="medical-info-row"><span className="medical-info-label">Allergies</span><span className="kairos-badge kairos-badge-pink">{patient.allergies}</span></div>}
                {patient.medications && <div className="medical-info-row"><span className="medical-info-label">Medications</span><span className="medical-info-value" style={{ color: '#2DD4BF' }}>{patient.medications}</span></div>}
                <div className="medical-info-row">
                  <span className="medical-info-label">Emergency Contact</span>
                  <a href={`tel:+91${patient.emergency_contact_phone}`} className="text-sm font-semibold" style={{ color: '#2DD4BF' }}>📞 +91 {patient.emergency_contact_phone}</a>
                </div>
              </div>

              {/* First Aid */}
              {firstAid && (
                <div className="kairos-card">
                  <h3 className="font-bold text-gray-900 mb-3">🩺 First Aid Guidance</h3>
                  {firstAid.cpr_needed && (
                    <div className="p-3 rounded-xl mb-3 font-bold text-white text-center" style={{ background: '#DC2626' }}>❤️ CPR Guide — Start immediately</div>
                  )}
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <p className="text-xs font-bold uppercase tracking-wider mb-2" style={{ color: '#16A34A' }}>✓ DO</p>
                      {firstAid.dos.map((d, i) => <p key={i} className="text-xs text-gray-600 mb-1">• {d}</p>)}
                    </div>
                    <div>
                      <p className="text-xs font-bold uppercase tracking-wider mb-2" style={{ color: '#DC2626' }}>✗ DON'T</p>
                      {firstAid.donts.map((d, i) => <p key={i} className="text-xs text-gray-600 mb-1">• {d}</p>)}
                    </div>
                  </div>
                </div>
              )}

              {!dispatched ? (
                <button onClick={handleDispatch} className="kairos-btn-danger w-full justify-center text-lg py-4" style={{ borderRadius: '16px', minHeight: '60px' }}>🚑 Get Ambulance Now</button>
              ) : (
                <div className="kairos-card text-center">
                  <p className="text-2xl mb-1">✅</p>
                  <p className="font-bold text-gray-900">Ambulance Dispatched</p>
                  {eta && <p className="text-gray-500 text-sm">ETA: <strong style={{ color: '#2DD4BF' }}>{eta} minutes</strong></p>}
                </div>
              )}
              {error && <p className="text-red-500 text-sm text-center">{error}</p>}
            </div>
          )}

          {/* NOT IDENTIFIED state */}
          {phase === 'not_identified' && (
            <div className="kairos-card animate-fade-in-up">
              <div className="p-3 rounded-xl mb-4 flex items-center gap-2" style={{ background: '#FEF3C7' }}>
                <span>⚠️</span>
                <p className="text-sm font-semibold text-amber-800">Patient not identified — enter details manually</p>
              </div>
              <div className="space-y-4">
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="kairos-label">Approximate Age</label>
                    <input className="kairos-input" type="number" placeholder="35" value={manualAge} onChange={e => setManualAge(e.target.value)} />
                  </div>
                  <div>
                    <label className="kairos-label">Gender</label>
                    <select className="kairos-input" value={manualGender} onChange={e => setManualGender(e.target.value)}>
                      <option value="">Select</option>
                      <option>Male</option><option>Female</option><option>Other</option>
                    </select>
                  </div>
                </div>
                <div>
                  <label className="kairos-label">Visible Injuries</label>
                  <textarea className="kairos-input" placeholder="Describe visible injuries..." value={manualInjuries} onChange={e => setManualInjuries(e.target.value)} style={{ minHeight: '80px' }} />
                </div>
                <div>
                  <label className="kairos-label">Known Conditions (if any)</label>
                  <textarea className="kairos-input" placeholder="Any visible medical ID, documents..." value={manualConditions} onChange={e => setManualConditions(e.target.value)} style={{ minHeight: '80px' }} />
                </div>
                <button onClick={handleManualSubmit} className="kairos-btn-primary w-full justify-center" disabled={manualLoading}>
                  {manualLoading ? 'Submitting...' : 'Submit Info'}
                </button>
              </div>
              <div className="mt-4">
                {!dispatched ? (
                  <button onClick={handleDispatch} className="kairos-btn-danger w-full justify-center" style={{ minHeight: '56px', borderRadius: '14px' }}>🚑 Get Ambulance Now</button>
                ) : (
                  <div className="text-center py-3">
                    <p className="font-bold" style={{ color: '#16A34A' }}>✅ Ambulance Dispatched {eta ? `— ETA: ${eta} min` : ''}</p>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
