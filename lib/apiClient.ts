// Kairos AI — API Client
// All backend calls go through here. Frontend NEVER writes directly to Firebase.

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';

export const api = {
  // ── Registration ──────────────────────────────────────────
  async register(formData: FormData) {
    const res = await fetch(`${BACKEND_URL}/api/register`, {
      method: 'POST',
      body: formData,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Registration failed: ${res.status}`);
    }
    return res.json();
  },

  // ── Emergency ─────────────────────────────────────────────
  async checkNearby(lat: number, lng: number) {
    const res = await fetch(`${BACKEND_URL}/api/emergency/nearby?lat=${lat}&lng=${lng}`);
    if (!res.ok) throw new Error('Nearby check failed');
    return res.json();
  },

  async identify(formData: FormData) {
    const res = await fetch(`${BACKEND_URL}/api/emergency/identify`, {
      method: 'POST',
      body: formData,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Identification failed');
    }
    return res.json();
  },

  async submitManualInfo(emergencyId: string, formData: FormData) {
    const res = await fetch(`${BACKEND_URL}/api/emergency/${emergencyId}/manual`, {
      method: 'POST',
      body: formData,
    });
    if (!res.ok) throw new Error('Manual info submission failed');
    return res.json();
  },

  async dispatch(emergencyId: string) {
    const res = await fetch(`${BACKEND_URL}/api/emergency/${emergencyId}/dispatch`, {
      method: 'POST',
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Dispatch failed');
    }
    return res.json();
  },

  async getRoutingStatus(emergencyId: string) {
    const res = await fetch(`${BACKEND_URL}/api/emergency/${emergencyId}/routing-status`);
    if (!res.ok) throw new Error('Routing status fetch failed');
    return res.json();
  },

  async getAmbulanceLocation(emergencyId: string) {
    const res = await fetch(`${BACKEND_URL}/api/emergency/${emergencyId}/ambulance-location`);
    if (!res.ok) throw new Error('Ambulance location fetch failed');
    return res.json();
  },

  async submitCondition(emergencyId: string, data: {
    symptoms: string;
    vitals?: string;
    consciousness_level?: string;
    visible_injuries?: string;
  }) {
    const res = await fetch(`${BACKEND_URL}/api/emergency/${emergencyId}/condition`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    if (!res.ok) throw new Error('Condition submission failed');
    return res.json();
  },

  // ── Driver ────────────────────────────────────────────────
  async driverLogin(ambulanceId: string, driverPhone: string) {
    const res = await fetch(`${BACKEND_URL}/api/driver/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ambulance_id: ambulanceId, driver_phone: driverPhone }),
    });
    if (!res.ok) throw new Error('Login failed');
    return res.json();
  },

  async getDriverDashboard(ambulanceId: string) {
    const res = await fetch(`${BACKEND_URL}/api/driver/${ambulanceId}/dashboard`);
    if (!res.ok) throw new Error('Dashboard fetch failed');
    return res.json();
  },

  async getDriverStatus(ambulanceId: string) {
    const res = await fetch(`${BACKEND_URL}/api/driver/${ambulanceId}/status`);
    if (!res.ok) throw new Error('Status fetch failed');
    return res.json();
  },

  async getDriverNotifications(ambulanceId: string) {
    const res = await fetch(`${BACKEND_URL}/api/driver/${ambulanceId}/notifications`);
    if (!res.ok) throw new Error('Notifications fetch failed');
    return res.json();
  },

  async markNotificationRead(ambulanceId: string, notificationId: string) {
    const res = await fetch(`${BACKEND_URL}/api/driver/${ambulanceId}/notifications/${notificationId}/read`, {
      method: 'POST',
    });
    if (!res.ok) throw new Error('Mark read failed');
    return res.json();
  },

  async completeEmergency(ambulanceId: string) {
    const res = await fetch(`${BACKEND_URL}/api/driver/${ambulanceId}/complete`, {
      method: 'POST',
    });
    if (!res.ok) throw new Error('Complete failed');
    return res.json();
  },

  // ── Hospital ──────────────────────────────────────────────
  async getHospitalStatus(hospitalId: string) {
    const res = await fetch(`${BACKEND_URL}/api/hospital/${hospitalId}/status`);
    if (!res.ok) throw new Error('Hospital status fetch failed');
    return res.json();
  },

  async confirmBed(hospitalId: string, emergencyId: string, status: 'confirmed' | 'unavailable') {
    const res = await fetch(`${BACKEND_URL}/api/hospital/${hospitalId}/confirm-bed`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ emergency_id: emergencyId, status }),
    });
    if (!res.ok) throw new Error('Bed confirmation failed');
    return res.json();
  },

  async acknowledgeAlert(hospitalId: string) {
    const res = await fetch(`${BACKEND_URL}/api/hospital/${hospitalId}/acknowledge`, {
      method: 'POST',
    });
    if (!res.ok) throw new Error('Acknowledge failed');
    return res.json();
  },

  async getHospitalAmbulanceLocation(hospitalId: string) {
    const res = await fetch(`${BACKEND_URL}/api/hospital/${hospitalId}/ambulance-location`);
    if (!res.ok) throw new Error('Ambulance location fetch failed');
    return res.json();
  },

  // ── Simulation ────────────────────────────────────────────
  async startSimulation(emergencyId: string, ambulanceId: string, speed: number = 2) {
    const res = await fetch(
      `${BACKEND_URL}/api/simulation/start?emergency_id=${emergencyId}&ambulance_id=${ambulanceId}&speed=${speed}`,
      { method: 'POST' }
    );
    if (!res.ok) throw new Error('Simulation start failed');
    return res.json();
  },

  async getSimulationStatus(emergencyId: string) {
    const res = await fetch(`${BACKEND_URL}/api/simulation/status/${emergencyId}`);
    if (!res.ok) throw new Error('Simulation status failed');
    return res.json();
  },
};

export default api;
