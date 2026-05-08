'use client';

import { useState, useRef, useEffect } from 'react';
import Link from 'next/link';
import api from '@/lib/apiClient';

type Step = 'personal' | 'medical' | 'photos' | 'success';

const BLOOD_GROUPS = ['A+', 'A-', 'B+', 'B-', 'O+', 'O-', 'AB+', 'AB-'];

const PHOTO_LABELS = [
  'Front-facing',
  'Slight left angle',
  'Slight right angle',
  'With glasses (optional)',
  'Without glasses (optional)',
];

interface PhotoSlot {
  file: File | null;
  preview: string | null;
}

export default function RegisterPage() {
  const [step, setStep] = useState<Step>('personal');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Form fields
  const [name, setName] = useState('');
  const [age, setAge] = useState('');
  const [bloodGroup, setBloodGroup] = useState('');
  const [conditions, setConditions] = useState('');
  const [allergies, setAllergies] = useState('');
  const [medications, setMedications] = useState('');
  const [emergencyContactName, setEmergencyContactName] = useState('');
  const [emergencyContactPhone, setEmergencyContactPhone] = useState('');

  // Photos
  const [photos, setPhotos] = useState<PhotoSlot[]>(
    Array(5).fill(null).map(() => ({ file: null, preview: null }))
  );

  // Success
  const [qrCode, setQrCode] = useState<string | null>(null);
  const [userId, setUserId] = useState<string | null>(null);

  const fileInputRefs = useRef<(HTMLInputElement | null)[]>([]);

  const photoCount = photos.filter(p => p.file !== null).length;
  const canSubmit = name && age && bloodGroup && emergencyContactName && emergencyContactPhone && photoCount >= 3;

  // Phone validation
  const phoneValid = /^[6-9]\d{9}$/.test(emergencyContactPhone);
  const ageValid = Number(age) >= 1 && Number(age) <= 120;

  const handlePhotoChange = (index: number, file: File | null) => {
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (e) => {
      const updated = [...photos];
      updated[index] = { file, preview: e.target?.result as string };
      setPhotos(updated);
    };
    reader.readAsDataURL(file);
  };

  const removePhoto = (index: number) => {
    const updated = [...photos];
    updated[index] = { file: null, preview: null };
    setPhotos(updated);
    if (fileInputRefs.current[index]) {
      fileInputRefs.current[index]!.value = '';
    }
  };

  const handleSubmit = async () => {
    setError(null);
    if (!phoneValid) { setError('Phone must be a valid 10-digit Indian mobile number (starts with 6-9).'); return; }
    if (!ageValid) { setError('Age must be between 1 and 120.'); return; }
    if (photoCount < 3) { setError('Please upload at least 3 photos.'); return; }

    setLoading(true);
    try {
      const formData = new FormData();
      formData.append('name', name);
      formData.append('age', age);
      formData.append('blood_group', bloodGroup);
      if (conditions) formData.append('conditions', conditions);
      if (allergies) formData.append('allergies', allergies);
      if (medications) formData.append('medications', medications);
      formData.append('emergency_contact_name', emergencyContactName);
      formData.append('emergency_contact_phone', emergencyContactPhone);
      photos.filter(p => p.file).forEach(p => formData.append('photos', p.file!));

      const result = await api.register(formData);
      setQrCode(result.qr_code_base64);
      setUserId(result.user_id);
      setStep('success');
    } catch (err: any) {
      setError(err.message || 'Registration failed. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const stepNumber = { personal: 1, medical: 2, photos: 3, success: 4 }[step];

  return (
    <div className="min-h-screen" style={{ background: '#F0FDF9' }}>
      {/* ── Header ─── */}
      <header className="bg-white border-b border-gray-100 px-6 py-4 flex items-center gap-4">
        <Link href="/" className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg flex items-center justify-center font-bold text-white text-sm" style={{ background: '#2DD4BF' }}>K</div>
          <span className="font-bold text-gray-900">KAIROS</span>
        </Link>
        <span className="text-gray-300">/</span>
        <span className="text-sm font-medium text-gray-600">Citizen Registration</span>
      </header>

      <div className="max-w-2xl mx-auto px-4 py-8">
        {/* ── Progress ─── */}
        {step !== 'success' && (
          <div className="mb-8">
            <div className="flex items-center gap-2 mb-4">
              {['Personal Info', 'Medical Info', 'Face Photos'].map((s, i) => (
                <div key={i} className="flex items-center gap-2">
                  <div
                    className="w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold transition-all"
                    style={{
                      background: i + 1 <= stepNumber ? '#2DD4BF' : '#E2E8F0',
                      color: i + 1 <= stepNumber ? 'white' : '#94A3B8'
                    }}
                  >
                    {i + 1 < stepNumber ? '✓' : i + 1}
                  </div>
                  <span className="text-sm font-medium hidden md:block" style={{ color: i + 1 === stepNumber ? '#0F172A' : '#94A3B8' }}>{s}</span>
                  {i < 2 && <div className="w-8 h-0.5 bg-gray-200" />}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* ── Error ─── */}
        {error && (
          <div className="mb-4 p-4 rounded-xl border-2 flex items-start gap-3" style={{ background: '#FEE2E2', borderColor: '#DC2626' }}>
            <span className="text-lg">⚠️</span>
            <p className="text-sm font-medium" style={{ color: '#DC2626' }}>{error}</p>
          </div>
        )}

        {/* ─── STEP 1: Personal Info ─── */}
        {step === 'personal' && (
          <div className="kairos-card">
            <h1 className="text-2xl font-bold text-gray-900 mb-1">Personal Information</h1>
            <p className="text-sm text-gray-500 mb-6">This information will be used to identify you in emergencies.</p>

            <div className="space-y-5">
              <div>
                <label className="kairos-label" htmlFor="name">Full Name *</label>
                <input id="name" className="kairos-input" placeholder="Ananya Sharma" value={name} onChange={e => setName(e.target.value)} required />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="kairos-label" htmlFor="age">Age *</label>
                  <input id="age" type="number" min={1} max={120} className="kairos-input" placeholder="24" value={age} onChange={e => setAge(e.target.value)} required />
                </div>
                <div>
                  <label className="kairos-label" htmlFor="blood">Blood Group *</label>
                  <select id="blood" className="kairos-input" value={bloodGroup} onChange={e => setBloodGroup(e.target.value)} required>
                    <option value="">Select...</option>
                    {BLOOD_GROUPS.map(g => <option key={g} value={g}>{g}</option>)}
                  </select>
                </div>
              </div>
              <div>
                <label className="kairos-label" htmlFor="ecname">Emergency Contact Name *</label>
                <input id="ecname" className="kairos-input" placeholder="Rahul Sharma" value={emergencyContactName} onChange={e => setEmergencyContactName(e.target.value)} required />
              </div>
              <div>
                <label className="kairos-label" htmlFor="ecphone">Emergency Contact Phone *</label>
                <div className="relative">
                  <span className="absolute left-4 top-1/2 -translate-y-1/2 text-gray-400 text-sm">+91</span>
                  <input
                    id="ecphone"
                    type="tel"
                    className="kairos-input pl-12"
                    placeholder="9876543210"
                    value={emergencyContactPhone}
                    onChange={e => setEmergencyContactPhone(e.target.value.replace(/\D/g, '').slice(0, 10))}
                    required
                  />
                </div>
                {emergencyContactPhone && !phoneValid && (
                  <p className="text-xs mt-1" style={{ color: '#DC2626' }}>Must start with 6-9 and be 10 digits</p>
                )}
              </div>
            </div>

            <div className="mt-8 flex justify-end">
              <button
                className="kairos-btn-primary"
                onClick={() => setStep('medical')}
                disabled={!name || !age || !bloodGroup || !emergencyContactName || !emergencyContactPhone || !phoneValid || !ageValid}
                style={{ opacity: (!name || !age || !bloodGroup || !emergencyContactName || !emergencyContactPhone || !phoneValid || !ageValid) ? 0.5 : 1 }}
              >
                Next: Medical Info →
              </button>
            </div>
          </div>
        )}

        {/* ─── STEP 2: Medical Info ─── */}
        {step === 'medical' && (
          <div className="kairos-card">
            <h2 className="text-2xl font-bold text-gray-900 mb-1">Medical Information</h2>
            <p className="text-sm text-gray-500 mb-6">Optional but life-saving. Helps emergency teams provide better care.</p>

            <div className="space-y-5">
              <div>
                <label className="kairos-label" htmlFor="conditions">Prior Medical Conditions</label>
                <textarea id="conditions" className="kairos-input min-h-[100px] resize-none" placeholder="e.g. Diabetes Type 2, Asthma..." value={conditions} onChange={e => setConditions(e.target.value)} style={{ height: 'auto' }} />
              </div>
              <div>
                <label className="kairos-label" htmlFor="allergies">Known Allergies</label>
                <textarea id="allergies" className="kairos-input min-h-[100px] resize-none" placeholder="e.g. Penicillin, Dust mites..." value={allergies} onChange={e => setAllergies(e.target.value)} style={{ height: 'auto' }} />
              </div>
              <div>
                <label className="kairos-label" htmlFor="medications">Current Medications</label>
                <textarea id="medications" className="kairos-input min-h-[100px] resize-none" placeholder="e.g. Metformin 500mg, Montelukast 10mg..." value={medications} onChange={e => setMedications(e.target.value)} style={{ height: 'auto' }} />
              </div>
            </div>

            <div className="mt-8 flex justify-between">
              <button className="kairos-btn-secondary" onClick={() => setStep('personal')}>← Back</button>
              <button className="kairos-btn-primary" onClick={() => setStep('photos')}>Next: Face Photos →</button>
            </div>
          </div>
        )}

        {/* ─── STEP 3: Photos ─── */}
        {step === 'photos' && (
          <div className="kairos-card">
            <h2 className="text-2xl font-bold text-gray-900 mb-1">Face Registration Photos</h2>
            <p className="text-sm text-gray-500 mb-2">Upload 3–5 clear photos for AI identification. <strong>Minimum 3 required.</strong></p>
            <div className="flex items-center gap-2 mb-6">
              <div className="px-3 py-1 rounded-full text-xs font-bold" style={{ background: photoCount >= 3 ? '#DCFCE7' : '#FEE2E2', color: photoCount >= 3 ? '#16A34A' : '#DC2626' }}>
                {photoCount}/5 photos uploaded {photoCount >= 3 ? '✓' : `(need ${3 - photoCount} more)`}
              </div>
            </div>

            <div className="space-y-3">
              {PHOTO_LABELS.map((label, i) => (
                <div key={i} className="border-2 rounded-xl p-4 transition-all" style={{ borderColor: photos[i].file ? '#2DD4BF' : '#E2E8F0', background: photos[i].file ? '#F0FDF9' : 'white' }}>
                  <div className="flex items-center gap-4">
                    {/* Preview */}
                    <div className="w-16 h-16 rounded-lg overflow-hidden flex-shrink-0 border border-gray-200" style={{ background: '#F8FAFC' }}>
                      {photos[i].preview ? (
                        <img src={photos[i].preview!} alt={label} className="w-full h-full object-cover" />
                      ) : (
                        <div className="w-full h-full flex items-center justify-center">
                          <svg className="w-6 h-6 text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                          </svg>
                        </div>
                      )}
                    </div>

                    <div className="flex-1">
                      <p className="text-sm font-semibold text-gray-700">{label}</p>
                      <p className="text-xs text-gray-400">
                        {i < 3 ? 'Required' : 'Optional'} · Clear face visible, good lighting
                      </p>
                    </div>

                    <div className="flex gap-2">
                      {photos[i].file && (
                        <button
                          onClick={() => removePhoto(i)}
                          className="w-9 h-9 rounded-lg flex items-center justify-center text-gray-400 hover:text-red-500 hover:bg-red-50 transition-colors"
                        >
                          ✕
                        </button>
                      )}
                      <button
                        onClick={() => fileInputRefs.current[i]?.click()}
                        className="px-4 py-2 rounded-lg text-sm font-semibold transition-all"
                        style={{ background: photos[i].file ? '#CCFBF1' : '#2DD4BF', color: photos[i].file ? '#0F766E' : 'white', minHeight: '36px' }}
                      >
                        {photos[i].file ? 'Change' : 'Upload'}
                      </button>
                      <input
                        ref={el => { fileInputRefs.current[i] = el; }}
                        type="file"
                        accept="image/*"
                        className="hidden"
                        onChange={e => handlePhotoChange(i, e.target.files?.[0] || null)}
                      />
                    </div>
                  </div>
                </div>
              ))}
            </div>

            <div className="mt-8 flex justify-between">
              <button className="kairos-btn-secondary" onClick={() => setStep('medical')}>← Back</button>
              <button
                className="kairos-btn-primary"
                onClick={handleSubmit}
                disabled={photoCount < 3 || loading}
                style={{ opacity: (photoCount < 3 || loading) ? 0.5 : 1, minWidth: '160px' }}
              >
                {loading ? (
                  <span className="flex items-center gap-2">
                    <span className="spinner w-4 h-4" style={{ borderWidth: '2px' }}></span>
                    Generating identity...
                  </span>
                ) : (
                  '✓ Register Now'
                )}
              </button>
            </div>
          </div>
        )}

        {/* ─── SUCCESS ─── */}
        {step === 'success' && (
          <div className="kairos-card text-center">
            <div className="w-20 h-20 rounded-full flex items-center justify-center mx-auto mb-6" style={{ background: '#DCFCE7' }}>
              <svg className="w-10 h-10" style={{ color: '#16A34A' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>

            <h2 className="text-2xl font-bold text-gray-900 mb-2">You are now identifiable in any emergency.</h2>
            <p className="text-gray-500 mb-8">Your medical identity has been securely registered. In an emergency, a photo of your face is all that's needed to retrieve your medical profile.</p>

            {/* QR Code */}
            {qrCode && (
              <div className="mb-6">
                <p className="text-sm font-semibold text-gray-600 mb-4 uppercase tracking-wider">Your Emergency QR Code</p>
                <div className="inline-block p-4 bg-white rounded-2xl border-2 shadow-lg" style={{ borderColor: '#2DD4BF' }}>
                  <img src={`data:image/png;base64,${qrCode}`} alt="Emergency QR Code" className="w-48 h-48 mx-auto" />
                </div>
                <p className="text-xs text-gray-400 mt-2">Scan to see your emergency profile</p>
              </div>
            )}

            {/* Wallet Card */}
            <div className="rounded-xl p-4 mb-6 text-left" style={{ background: '#F0FDF9', border: '1px solid #2DD4BF' }}>
              <p className="text-xs font-bold text-gray-500 uppercase tracking-wider mb-3">Emergency Wallet Card</p>
              <div className="space-y-2">
                <div className="flex justify-between">
                  <span className="text-sm text-gray-500">Name</span>
                  <span className="text-sm font-semibold">{name}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-sm text-gray-500">Blood Group</span>
                  <span className="kairos-badge kairos-badge-teal">{bloodGroup}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-sm text-gray-500">Emergency Contact</span>
                  <span className="text-sm font-semibold">+91 {emergencyContactPhone}</span>
                </div>
              </div>
            </div>

            <div className="flex gap-3 justify-center flex-wrap">
              <button
                className="kairos-btn-primary"
                onClick={() => window.print()}
              >
                🖨️ Print / Download
              </button>
              <button
                className="kairos-btn-secondary"
                onClick={() => {
                  setStep('personal');
                  setName(''); setAge(''); setBloodGroup('');
                  setConditions(''); setAllergies(''); setMedications('');
                  setEmergencyContactName(''); setEmergencyContactPhone('');
                  setPhotos(Array(5).fill(null).map(() => ({ file: null, preview: null })));
                  setQrCode(null);
                }}
              >
                Update my profile
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
