import { useEffect, useState } from 'react'
import { CheckCircle, Loader2 } from 'lucide-react'
import type { WizardData } from '../App'

interface Props {
  data: WizardData
}

const T = {
  en: {
    title: 'Setup Complete!',
    saving: 'Saving configuration...',
    restarting: 'Restarting MoMo...',
    redirect: 'Redirecting to dashboard...',
    done: 'All done!',
    instruction: 'Connect to your management network:',
    ssid: 'Network',
    url: 'Dashboard',
    tip: 'This page will redirect automatically, or click the link above.',
  },
  tr: {
    title: 'Kurulum Tamamlandı!',
    saving: 'Yapılandırma kaydediliyor...',
    restarting: 'MoMo yeniden başlatılıyor...',
    redirect: 'Panele yönlendiriliyor...',
    done: 'Tamam!',
    instruction: 'Yönetim ağına bağlan:',
    ssid: 'Ağ',
    url: 'Panel',
    tip: 'Bu sayfa otomatik yönlendirecek, veya yukarıdaki linke tıkla.',
  },
}

export function Complete({ data }: Props) {
  const t = T[data.language]
  const [stage, setStage] = useState(0)

  useEffect(() => {
    const timers = [
      setTimeout(() => setStage(1), 2000),
      setTimeout(() => setStage(2), 4000),
      setTimeout(() => setStage(3), 6000),
    ]
    return () => timers.forEach(clearTimeout)
  }, [])

  const dashboardUrl = data.network.mode === 'ap' 
    ? 'http://192.168.4.1:8082'
    : 'http://momo.local:8082'

  const ssid = data.network.mode === 'ap'
    ? data.network.ap_ssid
    : data.network.client_ssid

  return (
    <div className="flex flex-col h-full items-center justify-center text-center">
      {/* Success Animation */}
      <div className="relative mb-8">
        <div className="w-24 h-24 rounded-full bg-accent-green/20 flex items-center justify-center">
          {stage < 3 ? (
            <Loader2 className="w-12 h-12 text-accent-green animate-spin" />
          ) : (
            <CheckCircle className="w-12 h-12 text-accent-green animate-fade-in" />
          )}
        </div>
        <div className="absolute inset-0 rounded-full bg-accent-green/10 animate-ping" />
      </div>

      {/* Title */}
      <h1 className="text-2xl font-bold text-text-primary mb-2">{t.title}</h1>

      {/* Progress Steps */}
      <div className="space-y-3 mb-8">
        <ProgressStep active={stage >= 0} complete={stage > 0} text={t.saving} />
        <ProgressStep active={stage >= 1} complete={stage > 1} text={t.restarting} />
        <ProgressStep active={stage >= 2} complete={stage > 2} text={t.redirect} />
      </div>

      {/* Connection Info */}
      {stage >= 2 && (
        <div className="card w-full max-w-sm animate-fade-in">
          <p className="text-sm text-text-muted mb-4">{t.instruction}</p>
          
          <div className="space-y-3">
            <div className="flex justify-between">
              <span className="text-text-muted">{t.ssid}</span>
              <span className="font-mono text-accent-cyan">{ssid}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-text-muted">{t.url}</span>
              <a 
                href={dashboardUrl}
                className="font-mono text-accent-green hover:underline"
              >
                {dashboardUrl}
              </a>
            </div>
          </div>

          <p className="text-xs text-text-muted mt-4">{t.tip}</p>
        </div>
      )}

      {/* MoMo Branding */}
      <div className="mt-auto pt-8 text-text-muted text-sm">
        <span className="text-2xl">🔥</span>
        <p className="mt-2">MoMo Ecosystem</p>
      </div>
    </div>
  )
}

function ProgressStep({ active, complete, text }: { active: boolean; complete: boolean; text: string }) {
  return (
    <div className={`flex items-center gap-3 ${active ? 'text-text-primary' : 'text-text-muted'}`}>
      <div className={`w-5 h-5 rounded-full flex items-center justify-center ${
        complete ? 'bg-accent-green' : active ? 'bg-momo-surface border border-border-default' : 'bg-momo-surface'
      }`}>
        {complete ? (
          <CheckCircle className="w-4 h-4 text-momo-bg" />
        ) : active ? (
          <Loader2 className="w-3 h-3 animate-spin" />
        ) : null}
      </div>
      <span className="text-sm">{text}</span>
    </div>
  )
}

