import { useState, useEffect } from 'react'
import { Wifi, Router, Signal, Lock, RefreshCw, ArrowRight, ArrowLeft } from 'lucide-react'
import type { WizardData } from '../App'

interface Props {
  data: WizardData
  updateData: (updates: Partial<WizardData>) => void
  goNext: () => void
  goBack: () => void
  loading: boolean
  setLoading: (loading: boolean) => void
}

interface WifiNetwork {
  ssid: string
  bssid: string
  signal: number
  encryption: string
}

const T = {
  en: {
    title: 'Management Network',
    subtitle: 'How will you access MoMo after setup?',
    createAP: 'Create WiFi Hotspot',
    createAPDesc: 'MoMo creates its own WiFi network (recommended)',
    joinNetwork: 'Connect to existing WiFi',
    joinNetworkDesc: 'MoMo joins your home/office network',
    apName: 'Network Name (SSID)',
    apPassword: 'Password (min 8 chars)',
    selectWifi: 'Select WiFi Network',
    scanning: 'Scanning...',
    refresh: 'Refresh',
    wifiPassword: 'WiFi Password',
    back: 'Back',
    next: 'Next',
    errorShort: 'Password must be at least 8 characters',
    errorNoSSID: 'Please select a WiFi network',
  },
  tr: {
    title: 'Yönetim Ağı',
    subtitle: 'Kurulumdan sonra MoMo\'ya nasıl erişeceksin?',
    createAP: 'WiFi Hotspot Oluştur',
    createAPDesc: 'MoMo kendi WiFi ağını oluşturur (önerilen)',
    joinNetwork: 'Mevcut WiFi\'a Bağlan',
    joinNetworkDesc: 'MoMo ev/ofis ağına bağlanır',
    apName: 'Ağ Adı (SSID)',
    apPassword: 'Şifre (min 8 karakter)',
    selectWifi: 'WiFi Ağı Seç',
    scanning: 'Taranıyor...',
    refresh: 'Yenile',
    wifiPassword: 'WiFi Şifresi',
    back: 'Geri',
    next: 'İleri',
    errorShort: 'Şifre en az 8 karakter olmalı',
    errorNoSSID: 'Lütfen bir WiFi ağı seçin',
  },
}

export function Network({ data, updateData, goNext, goBack, loading, setLoading }: Props) {
  const t = T[data.language]
  const [networks, setNetworks] = useState<WifiNetwork[]>([])
  const [scanning, setScanning] = useState(false)
  const [error, setError] = useState('')

  const mode = data.network.mode

  const scanNetworks = async () => {
    setScanning(true)
    try {
      const res = await fetch('/api/wifi/scan')
      const json = await res.json()
      setNetworks(json.networks || [])
    } catch {
      // API not available
    } finally {
      setScanning(false)
    }
  }

  useEffect(() => {
    if (mode === 'client') {
      scanNetworks()
    }
  }, [mode])

  const setMode = (newMode: 'ap' | 'client') => {
    updateData({
      network: { ...data.network, mode: newMode }
    })
  }

  const updateNetwork = (updates: Partial<WizardData['network']>) => {
    updateData({
      network: { ...data.network, ...updates }
    })
  }

  const selectWifi = (ssid: string) => {
    updateNetwork({ client_ssid: ssid })
  }

  const getSignalIcon = (signal: number) => {
    if (signal > -50) return '📶'
    if (signal > -70) return '📶'
    return '📶'
  }

  const canProceed = () => {
    if (mode === 'ap') {
      return data.network.ap_password.length >= 8
    } else {
      return data.network.client_ssid.length > 0
    }
  }

  const handleNext = async () => {
    setError('')

    if (mode === 'ap' && data.network.ap_password.length < 8) {
      setError(t.errorShort)
      return
    }

    if (mode === 'client' && !data.network.client_ssid) {
      setError(t.errorNoSSID)
      return
    }

    setLoading(true)

    try {
      await fetch('/api/step/network', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          mode,
          ap_ssid: data.network.ap_ssid,
          ap_password: data.network.ap_password,
          ap_channel: data.network.ap_channel,
          client_ssid: data.network.client_ssid,
          client_password: data.network.client_password,
        }),
      })
      goNext()
    } catch {
      setError('Connection error')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="mb-6">
        <div className="w-14 h-14 rounded-2xl bg-accent-cyan/10 flex items-center justify-center mb-4">
          <Wifi className="w-7 h-7 text-accent-cyan" />
        </div>
        <h1 className="text-2xl font-bold text-text-primary">{t.title}</h1>
        <p className="text-text-secondary mt-1">{t.subtitle}</p>
      </div>

      {/* Mode Selection */}
      <div className="space-y-3 mb-6">
        <button
          onClick={() => setMode('ap')}
          className={`option-card w-full ${mode === 'ap' ? 'selected' : ''}`}
        >
          <div className="option-icon">
            <Router className="w-6 h-6 text-accent-green" />
          </div>
          <div className="option-content text-left">
            <div className="option-title">{t.createAP}</div>
            <div className="option-desc">{t.createAPDesc}</div>
          </div>
        </button>

        <button
          onClick={() => setMode('client')}
          className={`option-card w-full ${mode === 'client' ? 'selected' : ''}`}
        >
          <div className="option-icon">
            <Signal className="w-6 h-6 text-accent-cyan" />
          </div>
          <div className="option-content text-left">
            <div className="option-title">{t.joinNetwork}</div>
            <div className="option-desc">{t.joinNetworkDesc}</div>
          </div>
        </button>
      </div>

      {/* Configuration */}
      <div className="flex-1 overflow-auto">
        {mode === 'ap' ? (
          <div className="card space-y-4">
            <div className="input-group mb-0">
              <label className="input-label">{t.apName}</label>
              <input
                type="text"
                value={data.network.ap_ssid}
                onChange={(e) => updateNetwork({ ap_ssid: e.target.value })}
                className="input"
                placeholder="MoMo-Management"
              />
            </div>
            <div className="input-group mb-0">
              <label className="input-label">{t.apPassword}</label>
              <div className="input-with-icon">
                <Lock className="input-icon w-5 h-5" />
                <input
                  type="password"
                  value={data.network.ap_password}
                  onChange={(e) => updateNetwork({ ap_password: e.target.value })}
                  className="input"
                  placeholder="••••••••"
                />
              </div>
            </div>
          </div>
        ) : (
          <div className="card">
            <div className="flex items-center justify-between mb-4">
              <span className="text-sm font-medium">{t.selectWifi}</span>
              <button
                onClick={scanNetworks}
                disabled={scanning}
                className="btn-ghost text-sm py-1 px-2"
              >
                <RefreshCw className={`w-4 h-4 ${scanning ? 'animate-spin' : ''}`} />
                {t.refresh}
              </button>
            </div>

            {scanning ? (
              <div className="text-center py-8 text-text-muted">
                <div className="loading-spinner mx-auto mb-2" />
                {t.scanning}
              </div>
            ) : (
              <div className="wifi-list">
                {networks.map((net) => (
                  <button
                    key={net.bssid}
                    onClick={() => selectWifi(net.ssid)}
                    className={`wifi-item w-full text-left ${
                      data.network.client_ssid === net.ssid ? 'selected' : ''
                    }`}
                  >
                    <span className="wifi-signal">{getSignalIcon(net.signal)}</span>
                    <span className="wifi-name">{net.ssid}</span>
                    <span className="wifi-security">{net.encryption.toUpperCase()}</span>
                  </button>
                ))}
                {networks.length === 0 && (
                  <div className="text-center py-4 text-text-muted text-sm">
                    No networks found
                  </div>
                )}
              </div>
            )}

            {data.network.client_ssid && (
              <div className="input-group mt-4 mb-0">
                <label className="input-label">{t.wifiPassword}</label>
                <input
                  type="password"
                  value={data.network.client_password}
                  onChange={(e) => updateNetwork({ client_password: e.target.value })}
                  className="input"
                  placeholder="••••••••"
                />
              </div>
            )}
          </div>
        )}

        {error && (
          <div className="input-error text-center mt-4">{error}</div>
        )}
      </div>

      {/* Actions */}
      <div className="wizard-footer">
        <button onClick={goBack} className="btn-secondary">
          <ArrowLeft className="w-5 h-5" />
          {t.back}
        </button>
        <button
          onClick={handleNext}
          disabled={!canProceed() || loading}
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

