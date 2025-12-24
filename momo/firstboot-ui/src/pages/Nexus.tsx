import { useState, useEffect } from 'react'
import { Link2, Search, Server, Check, ArrowRight, ArrowLeft, SkipForward } from 'lucide-react'
import type { WizardData } from '../App'

interface Props {
  data: WizardData
  updateData: (updates: Partial<WizardData>) => void
  goNext: () => void
  goBack: () => void
  loading: boolean
  setLoading: (loading: boolean) => void
}

interface NexusDevice {
  name: string
  ip: string
  port: number
  version: string
  devices_connected: number
}

const T = {
  en: {
    title: 'Connect to Nexus',
    subtitle: 'Optional: Link to your central command hub',
    features: [
      'Sync handshakes & credentials',
      'Cloud GPU cracking',
      'Fleet management',
      'Push notifications',
    ],
    scanning: 'Scanning for Nexus devices...',
    found: 'Found Nexus',
    version: 'Version',
    devices: 'devices connected',
    connect: 'Connect',
    manual: 'Enter Manually',
    nexusUrl: 'Nexus URL',
    deviceName: 'Device Name',
    deviceNameHint: 'How this device appears in Nexus',
    skip: 'Skip for now',
    skipHint: 'You can configure Nexus later',
    back: 'Back',
    next: 'Next',
    testing: 'Testing connection...',
    connected: 'Connected!',
    error: 'Connection failed',
  },
  tr: {
    title: 'Nexus\'a Bağlan',
    subtitle: 'Opsiyonel: Merkezi komuta merkezine bağlan',
    features: [
      'Handshake ve credential senkronizasyonu',
      'Cloud GPU kırma',
      'Filo yönetimi',
      'Push bildirimleri',
    ],
    scanning: 'Nexus cihazları taranıyor...',
    found: 'Nexus Bulundu',
    version: 'Versiyon',
    devices: 'cihaz bağlı',
    connect: 'Bağlan',
    manual: 'Manuel Gir',
    nexusUrl: 'Nexus URL',
    deviceName: 'Cihaz Adı',
    deviceNameHint: 'Bu cihaz Nexus\'ta nasıl görünecek',
    skip: 'Şimdilik atla',
    skipHint: 'Nexus\'u sonra ayarlayabilirsin',
    back: 'Geri',
    next: 'İleri',
    testing: 'Bağlantı test ediliyor...',
    connected: 'Bağlandı!',
    error: 'Bağlantı başarısız',
  },
}

export function Nexus({ data, updateData, goNext, goBack, loading, setLoading }: Props) {
  const t = T[data.language]
  const [devices, setDevices] = useState<NexusDevice[]>([])
  const [scanning, setScanning] = useState(false)
  const [showManual, setShowManual] = useState(false)
  const [testResult, setTestResult] = useState<'none' | 'testing' | 'success' | 'error'>('none')

  const updateNexus = (updates: Partial<WizardData['nexus']>) => {
    updateData({
      nexus: { ...data.nexus, ...updates }
    })
  }

  const scanDevices = async () => {
    setScanning(true)
    try {
      const res = await fetch('/api/nexus/discover')
      const json = await res.json()
      setDevices(json.devices || [])
    } catch {
      // API not available
    } finally {
      setScanning(false)
    }
  }

  useEffect(() => {
    scanDevices()
  }, [])

  const selectDevice = async (device: NexusDevice) => {
    const url = `http://${device.ip}:${device.port}`
    updateNexus({ enabled: true, url })
    
    setTestResult('testing')
    try {
      const res = await fetch(`/api/nexus/test?url=${encodeURIComponent(url)}`, {
        method: 'POST',
      })
      const json = await res.json()
      setTestResult(json.success ? 'success' : 'error')
    } catch {
      setTestResult('error')
    }
  }

  const testConnection = async () => {
    if (!data.nexus.url) return
    
    setTestResult('testing')
    try {
      const res = await fetch(`/api/nexus/test?url=${encodeURIComponent(data.nexus.url)}`, {
        method: 'POST',
      })
      const json = await res.json()
      setTestResult(json.success ? 'success' : 'error')
    } catch {
      setTestResult('error')
    }
  }

  const handleNext = async () => {
    setLoading(true)
    try {
      await fetch('/api/step/nexus', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data.nexus),
      })
      goNext()
    } catch {
      goNext()
    } finally {
      setLoading(false)
    }
  }

  const handleSkip = async () => {
    updateNexus({ enabled: false })
    handleNext()
  }

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="mb-6">
        <div className="w-14 h-14 rounded-2xl bg-accent-orange/10 flex items-center justify-center mb-4">
          <Link2 className="w-7 h-7 text-accent-orange" />
        </div>
        <h1 className="text-2xl font-bold text-text-primary">{t.title}</h1>
        <p className="text-text-secondary mt-1">{t.subtitle}</p>

        {/* Features */}
        <div className="flex flex-wrap gap-2 mt-4">
          {t.features.map((feature, i) => (
            <span key={i} className="text-xs px-2 py-1 rounded-full bg-momo-surface text-text-muted">
              ✓ {feature}
            </span>
          ))}
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-auto space-y-4">
        {/* Discovered Devices */}
        {scanning ? (
          <div className="card text-center py-8">
            <Search className="w-8 h-8 text-text-muted mx-auto mb-3 animate-pulse" />
            <p className="text-text-muted">{t.scanning}</p>
          </div>
        ) : devices.length > 0 ? (
          <div className="space-y-3">
            {devices.map((device) => (
              <button
                key={device.ip}
                onClick={() => selectDevice(device)}
                className={`card w-full text-left ${
                  data.nexus.url.includes(device.ip) ? 'border-accent-green bg-accent-green/5' : ''
                }`}
              >
                <div className="flex items-center gap-4">
                  <div className="w-12 h-12 rounded-xl bg-accent-green/10 flex items-center justify-center">
                    <Server className="w-6 h-6 text-accent-green" />
                  </div>
                  <div className="flex-1">
                    <div className="font-semibold">{device.name || t.found}</div>
                    <div className="text-sm text-text-muted">
                      {device.ip}:{device.port}
                    </div>
                    <div className="text-xs text-text-muted mt-1">
                      {t.version}: {device.version} • {device.devices_connected} {t.devices}
                    </div>
                  </div>
                  {data.nexus.url.includes(device.ip) && (
                    <div className="w-6 h-6 rounded-full bg-accent-green flex items-center justify-center">
                      <Check className="w-4 h-4 text-momo-bg" />
                    </div>
                  )}
                </div>
              </button>
            ))}
          </div>
        ) : null}

        {/* Manual Entry */}
        {showManual || devices.length === 0 ? (
          <div className="card space-y-4">
            <div className="input-group mb-0">
              <label className="input-label">{t.nexusUrl}</label>
              <input
                type="text"
                value={data.nexus.url}
                onChange={(e) => updateNexus({ url: e.target.value, enabled: true })}
                className="input"
                placeholder="http://192.168.1.100:8080"
              />
            </div>
            <div className="input-group mb-0">
              <label className="input-label">{t.deviceName}</label>
              <input
                type="text"
                value={data.nexus.device_name}
                onChange={(e) => updateNexus({ device_name: e.target.value })}
                className="input"
                placeholder="MoMo-Field-01"
              />
              <p className="input-hint">{t.deviceNameHint}</p>
            </div>
            
            {data.nexus.url && (
              <button
                onClick={testConnection}
                disabled={testResult === 'testing'}
                className="btn-secondary w-full"
              >
                {testResult === 'testing' ? (
                  <><div className="loading-spinner" /> {t.testing}</>
                ) : testResult === 'success' ? (
                  <><Check className="w-5 h-5 text-accent-green" /> {t.connected}</>
                ) : testResult === 'error' ? (
                  <span className="text-accent-red">{t.error}</span>
                ) : (
                  t.connect
                )}
              </button>
            )}
          </div>
        ) : (
          <button
            onClick={() => setShowManual(true)}
            className="btn-ghost w-full"
          >
            {t.manual}
          </button>
        )}

        {/* Skip Option */}
        <button
          onClick={handleSkip}
          className="flex items-center justify-center gap-2 w-full py-4 text-text-muted hover:text-text-primary transition-colors"
        >
          <SkipForward className="w-4 h-4" />
          <span>{t.skip}</span>
        </button>
        <p className="text-center text-xs text-text-muted">{t.skipHint}</p>
      </div>

      {/* Actions */}
      <div className="wizard-footer">
        <button onClick={goBack} className="btn-secondary">
          <ArrowLeft className="w-5 h-5" />
          {t.back}
        </button>
        <button
          onClick={handleNext}
          disabled={loading}
          className="btn-primary"
        >
          {loading ? (
            <div className="loading-spinner" />
          ) : (
            <>
              {t.next}
              <ArrowRight className="w-5 h-5" />
            </>
          )}
        </button>
      </div>
    </div>
  )
}

