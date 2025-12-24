import { CheckCircle, ArrowLeft, Rocket, Wifi, Target, Link2, Lock } from 'lucide-react'
import type { WizardData } from '../App'

interface Props {
  data: WizardData
  updateData: (updates: Partial<WizardData>) => void
  goNext: () => void
  goBack: () => void
  loading: boolean
  setLoading: (loading: boolean) => void
}

const T = {
  en: {
    title: 'Setup Complete!',
    subtitle: 'Review your configuration',
    language: 'Language',
    password: 'Admin Password',
    passwordSet: 'Set',
    networkMode: 'Network Mode',
    ap: 'WiFi Hotspot',
    client: 'Client Mode',
    ssid: 'SSID',
    profile: 'Profile',
    passive: 'Passive',
    balanced: 'Balanced',
    aggressive: 'Aggressive',
    nexus: 'Nexus',
    connected: 'Connected',
    notConfigured: 'Not configured',
    important: 'Important',
    note1: 'MoMo will save configuration',
    note2: 'This setup network will close',
    note3: 'MoMo will restart in normal mode',
    note4: 'Connect to your management network',
    back: 'Back',
    finish: 'Finish Setup',
  },
  tr: {
    title: 'Kurulum Tamamlandı!',
    subtitle: 'Yapılandırmanı gözden geçir',
    language: 'Dil',
    password: 'Yönetici Şifresi',
    passwordSet: 'Ayarlandı',
    networkMode: 'Ağ Modu',
    ap: 'WiFi Hotspot',
    client: 'İstemci Modu',
    ssid: 'SSID',
    profile: 'Profil',
    passive: 'Pasif',
    balanced: 'Dengeli',
    aggressive: 'Agresif',
    nexus: 'Nexus',
    connected: 'Bağlı',
    notConfigured: 'Yapılandırılmadı',
    important: 'Önemli',
    note1: 'MoMo yapılandırmayı kaydedecek',
    note2: 'Bu kurulum ağı kapanacak',
    note3: 'MoMo normal modda yeniden başlayacak',
    note4: 'Yönetim ağına bağlan',
    back: 'Geri',
    finish: 'Kurulumu Bitir',
  },
}

export function Summary({ data, goNext, goBack, loading, setLoading }: Props) {
  const t = T[data.language]

  const handleFinish = async () => {
    setLoading(true)
    try {
      const res = await fetch('/api/complete', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ confirm: true }),
      })
      
      if (res.ok) {
        goNext()
      }
    } catch {
      goNext() // Continue anyway
    } finally {
      setLoading(false)
    }
  }

  const getProfileText = () => {
    switch (data.profile) {
      case 'passive': return t.passive
      case 'balanced': return t.balanced
      case 'aggressive': return t.aggressive
    }
  }

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="text-center mb-6">
        <div className="w-16 h-16 rounded-full bg-accent-green/10 flex items-center justify-center mx-auto mb-4">
          <CheckCircle className="w-8 h-8 text-accent-green" />
        </div>
        <h1 className="text-2xl font-bold text-text-primary">{t.title}</h1>
        <p className="text-text-secondary mt-1">{t.subtitle}</p>
      </div>

      {/* Summary */}
      <div className="flex-1 space-y-3">
        <div className="card">
          {/* Language */}
          <div className="summary-item">
            <span className="summary-label">{t.language}</span>
            <span className="summary-value">
              {data.language === 'en' ? '🇬🇧 English' : '🇹🇷 Türkçe'}
            </span>
          </div>

          {/* Password */}
          <div className="summary-item">
            <span className="summary-label flex items-center gap-2">
              <Lock className="w-4 h-4" />
              {t.password}
            </span>
            <span className="summary-value text-accent-green">✓ {t.passwordSet}</span>
          </div>

          {/* Network */}
          <div className="summary-item">
            <span className="summary-label flex items-center gap-2">
              <Wifi className="w-4 h-4" />
              {t.networkMode}
            </span>
            <span className="summary-value">
              {data.network.mode === 'ap' ? t.ap : t.client}
            </span>
          </div>

          <div className="summary-item">
            <span className="summary-label pl-6">{t.ssid}</span>
            <span className="summary-value font-mono text-sm">
              {data.network.mode === 'ap' ? data.network.ap_ssid : data.network.client_ssid}
            </span>
          </div>

          {/* Profile */}
          <div className="summary-item">
            <span className="summary-label flex items-center gap-2">
              <Target className="w-4 h-4" />
              {t.profile}
            </span>
            <span className={`summary-value ${
              data.profile === 'aggressive' ? 'text-accent-orange' :
              data.profile === 'balanced' ? 'text-accent-green' :
              'text-accent-cyan'
            }`}>
              {getProfileText()}
            </span>
          </div>

          {/* Nexus */}
          <div className="summary-item border-b-0">
            <span className="summary-label flex items-center gap-2">
              <Link2 className="w-4 h-4" />
              {t.nexus}
            </span>
            <span className={`summary-value ${data.nexus.enabled ? 'text-accent-green' : 'text-text-muted'}`}>
              {data.nexus.enabled ? t.connected : t.notConfigured}
            </span>
          </div>
        </div>

        {/* Important Notes */}
        <div className="card bg-accent-orange/5 border-accent-orange/30">
          <h3 className="font-semibold text-accent-orange mb-3">⚠️ {t.important}</h3>
          <ol className="list-decimal list-inside space-y-2 text-sm text-text-secondary">
            <li>{t.note1}</li>
            <li>{t.note2}</li>
            <li>{t.note3}</li>
            <li>{t.note4}</li>
          </ol>
          
          {data.network.mode === 'ap' && (
            <div className="mt-4 p-3 bg-momo-bg rounded-lg">
              <p className="text-xs text-text-muted mb-1">After restart, connect to:</p>
              <p className="font-mono text-accent-cyan">{data.network.ap_ssid}</p>
              <p className="text-xs text-text-muted mt-1">
                Dashboard: http://192.168.4.1:8082
              </p>
            </div>
          )}
        </div>
      </div>

      {/* Actions */}
      <div className="wizard-footer">
        <button onClick={goBack} className="btn-secondary">
          <ArrowLeft className="w-5 h-5" />
          {t.back}
        </button>
        <button
          onClick={handleFinish}
          disabled={loading}
          className="btn-primary"
        >
          {loading ? (
            <div className="loading-spinner" />
          ) : (
            <>
              <Rocket className="w-5 h-5" />
              {t.finish}
            </>
          )}
        </button>
      </div>
    </div>
  )
}

