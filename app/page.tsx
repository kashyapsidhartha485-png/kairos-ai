import Link from 'next/link';

export default function Home() {
  return (
    <main className="min-h-screen bg-white">
      {/* ── Navbar ─── */}
      <nav className="flex items-center justify-between px-8 py-4 border-b border-gray-100">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg flex items-center justify-center font-bold text-white text-sm" style={{background:'#2DD4BF'}}>
            K
          </div>
          <span className="font-bold text-xl text-gray-900">KAIROS</span>
        </div>
        <div className="hidden md:flex items-center gap-8 text-sm font-medium text-gray-600">
          <a href="#features" className="hover:text-gray-900 transition-colors">Features</a>
          <a href="#dashboards" className="hover:text-gray-900 transition-colors">Dashboards</a>
          <a href="#howitworks" className="hover:text-gray-900 transition-colors">How it works</a>
        </div>
        <Link
          href="/emergency"
          className="px-5 py-2.5 rounded-xl font-semibold text-white text-sm transition-all hover:opacity-90"
          style={{background:'#2DD4BF', minHeight:'40px', display:'inline-flex', alignItems:'center'}}
        >
          Open App
        </Link>
      </nav>

      {/* ── Hero ─── */}
      <section className="px-8 pt-20 pb-16 text-center" style={{background:'#F0FDF9'}}>
        <h1 className="text-5xl md:text-6xl font-black text-gray-900 mb-4 leading-tight">
          Three roles. One mission.
        </h1>
        <p className="text-lg text-gray-500 mb-12 max-w-lg mx-auto">
          A purpose-built dashboard for everyone in the emergency chain.
        </p>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 max-w-4xl mx-auto">
          {/* Citizen */}
          <div className="bg-white rounded-2xl p-6 border border-gray-100 text-left shadow-sm hover:shadow-md transition-shadow">
            <div className="w-12 h-12 rounded-xl flex items-center justify-center mb-4" style={{background:'#CCFBF1'}}>
              <svg className="w-6 h-6" style={{color:'#2DD4BF'}} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
              </svg>
            </div>
            <h2 className="text-lg font-bold text-gray-900 mb-2">Citizen</h2>
            <p className="text-sm text-gray-500 mb-4">Pre-register your medical profile and call for help in one tap.</p>
            <Link href="/register" className="text-sm font-semibold flex items-center gap-1 hover:gap-2 transition-all" style={{color:'#2DD4BF'}}>
              Open dashboard →
            </Link>
          </div>

          {/* Paramedic */}
          <div className="bg-white rounded-2xl p-6 border border-gray-100 text-left shadow-sm hover:shadow-md transition-shadow">
            <div className="w-12 h-12 rounded-xl flex items-center justify-center mb-4" style={{background:'#CCFBF1'}}>
              <svg className="w-6 h-6" style={{color:'#2DD4BF'}} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7" />
              </svg>
            </div>
            <h2 className="text-lg font-bold text-gray-900 mb-2">Paramedic</h2>
            <p className="text-sm mb-4" style={{color:'#2DD4BF'}}>Live vitals capture, AI hospital match and dual-leg navigation.</p>
            <Link href="/driver/AMB-001" className="text-sm font-semibold flex items-center gap-1 hover:gap-2 transition-all" style={{color:'#2DD4BF'}}>
              Open dashboard →
            </Link>
          </div>

          {/* ER Hospital */}
          <div className="bg-white rounded-2xl p-6 border border-gray-100 text-left shadow-sm hover:shadow-md transition-shadow">
            <div className="w-12 h-12 rounded-xl flex items-center justify-center mb-4" style={{background:'#CCFBF1'}}>
              <svg className="w-6 h-6" style={{color:'#2DD4BF'}} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
              </svg>
            </div>
            <h2 className="text-lg font-bold text-gray-900 mb-2">ER Hospital</h2>
            <p className="text-sm mb-4" style={{color:'#2DD4BF'}}>See incoming patients early and prepare beds, blood and teams.</p>
            <Link href="/hospital/hospital-1" className="text-sm font-semibold flex items-center gap-1 hover:gap-2 transition-all" style={{color:'#2DD4BF'}}>
              Open dashboard →
            </Link>
          </div>
        </div>
      </section>

      {/* ── Features ─── */}
      <section id="features" className="px-8 py-16 bg-white">
        <div className="max-w-4xl mx-auto">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-12">
            <div className="text-center">
              <div className="w-12 h-12 rounded-xl flex items-center justify-center mx-auto mb-4" style={{background:'#CCFBF1'}}>
                <svg className="w-6 h-6" style={{color:'#2DD4BF'}} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
                </svg>
              </div>
              <h3 className="font-bold text-gray-900 mb-2">Face-ID profiles</h3>
              <p className="text-sm text-gray-500">Even unconscious patients are identified and matched with their full medical history.</p>
            </div>
            <div className="text-center">
              <div className="w-12 h-12 rounded-xl flex items-center justify-center mx-auto mb-4" style={{background:'#CCFBF1'}}>
                <svg className="w-6 h-6" style={{color:'#2DD4BF'}} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                </svg>
              </div>
              <h3 className="font-bold text-gray-900 mb-2">AI triage</h3>
              <p className="text-sm text-gray-500">Vitals stream into Gemini-powered triage that suggests bed type and equipment.</p>
            </div>
            <div className="text-center">
              <div className="w-12 h-12 rounded-xl flex items-center justify-center mx-auto mb-4" style={{background:'#CCFBF1'}}>
                <svg className="w-6 h-6" style={{color:'#2DD4BF'}} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
                </svg>
              </div>
              <h3 className="font-bold text-gray-900 mb-2">Dual-leg routing</h3>
              <p className="text-sm text-gray-500">Ambulance → Patient → Hospital. One map. No misses.</p>
            </div>
          </div>
        </div>
      </section>

      {/* ── Emergency CTA ─── */}
      <section className="px-8 py-16 text-center" style={{background:'#FFF1F2'}}>
        <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full text-sm font-semibold mb-6" style={{background:'#FEE2E2', color:'#DC2626'}}>
          🚨 Emergency Access
        </div>
        <h2 className="text-3xl font-black text-gray-900 mb-4">In an emergency right now?</h2>
        <p className="text-gray-500 mb-8">Tap below to immediately activate the emergency response system.</p>
        <Link
          href="/emergency"
          className="inline-flex items-center gap-3 px-8 py-4 rounded-2xl font-bold text-white text-lg shadow-lg hover:shadow-xl transition-all hover:scale-105"
          style={{background:'#DC2626', minHeight:'60px'}}
        >
          🆘 Activate Emergency
        </Link>
      </section>

      {/* ── Footer ─── */}
      <footer className="px-8 py-6 text-center text-sm text-gray-400 border-t border-gray-100">
        <p>© 2024 Kairos AI — DeepStation Google Hackathon · Built for BedBridge PRD v2.0</p>
      </footer>
    </main>
  );
}
