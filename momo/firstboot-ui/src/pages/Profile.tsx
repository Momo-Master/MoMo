import { Target, Eye, Zap, Flame, ArrowRight, ArrowLeft, Check, X } from 'lucide-react'
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
    title: 'Operation Profile',
    subtitle: 'Choose how MoMo will operate',
    passive: 'Passive',
    passiveDesc: 'Observation only. No attacks, just monitoring.',
    passiveTip: 'Safe for learning and reconnaissance',
    balanced: 'Balanced',
    balancedDesc: 'Smart targeting with stealth.',
    balancedTip: 'Recommended for most users',
    aggressive: 'Aggressive',
    aggressiveDesc: 'Maximum speed, all techniques enabled.',
    aggressiveTip: '⚠️ For authorized pentesting only!',
    wardriving: 'Wardriving',
    scanning: 'Scanning',
    attacks: 'Attacks',
    back: 'Back',
    next: 'Next',
  },
  tr: {
    title: 'Operasyon Profili',
    subtitle: 'MoMo nasıl çalışsın?',
    passive: 'Pasif',
    passiveDesc: 'Sadece gözlem. Saldırı yok, sadece izleme.',
    passiveTip: 'Öğrenmek ve keşif için güvenli',
    balanced: 'Dengeli',
    balancedDesc: 'Gizli modda akıllı hedefleme.',
    balancedTip: 'Çoğu kullanıcı için önerilen',
    aggressive: 'Agresif',
    aggressiveDesc: 'Maksimum hız, tüm teknikler aktif.',
    aggressiveTip: '⚠️ Sadece yetkili pentest için!',
    wardriving: 'Wardriving',
    scanning: 'Tarama',
    attacks: 'Saldırılar',
    back: 'Geri',
    next: 'İleri',
  },
}

type Profile = 'passive' | 'balanced' | 'aggressive'

interface ProfileOption {
  id: Profile
  icon: typeof Eye
  color: string
  features: { wardriving: boolean; scanning: boolean; attacks: boolean }
}

const profiles: ProfileOption[] = [
  { 
    id: 'passive', 
    icon: Eye, 
    color: 'text-accent-cyan',
    features: { wardriving: true, scanning: true, attacks: false }
  },
  { 
    id: 'balanced', 
    icon: Zap, 
    color: 'text-accent-green',
    features: { wardriving: true, scanning: true, attacks: true }
  },
  { 
    id: 'aggressive', 
    icon: Flame, 
    color: 'text-accent-orange',
    features: { wardriving: true, scanning: true, attacks: true }
  },
]

export function Profile({ data, updateData, goNext, goBack, loading, setLoading }: Props) {
  const t = T[data.language]

  const setProfile = (profile: Profile) => {
    updateData({ profile })
  }

  const handleNext = async () => {
    setLoading(true)
    try {
      await fetch('/api/step/profile', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ profile: data.profile }),
      })
      goNext()
    } catch {
      goNext() // Continue even if API fails
    } finally {
      setLoading(false)
    }
  }

  const getProfileText = (id: Profile) => {
    switch (id) {
      case 'passive':
        return { title: t.passive, desc: t.passiveDesc, tip: t.passiveTip }
      case 'balanced':
        return { title: t.balanced, desc: t.balancedDesc, tip: t.balancedTip }
      case 'aggressive':
        return { title: t.aggressive, desc: t.aggressiveDesc, tip: t.aggressiveTip }
    }
  }

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="mb-6">
        <div className="w-14 h-14 rounded-2xl bg-accent-purple/10 flex items-center justify-center mb-4">
          <Target className="w-7 h-7 text-accent-purple" />
        </div>
        <h1 className="text-2xl font-bold text-text-primary">{t.title}</h1>
        <p className="text-text-secondary mt-1">{t.subtitle}</p>
      </div>

      {/* Profile Options */}
      <div className="flex-1 space-y-4">
        {profiles.map((profile) => {
          const Icon = profile.icon
          const text = getProfileText(profile.id)
          const isSelected = data.profile === profile.id
          const isRecommended = profile.id === 'balanced'

          return (
            <button
              key={profile.id}
              onClick={() => setProfile(profile.id)}
              className={`card w-full text-left transition-all ${
                isSelected 
                  ? 'border-accent-green bg-accent-green/5 ring-2 ring-accent-green/20' 
                  : 'hover:border-border-active'
              }`}
            >
              <div className="flex items-start gap-4">
                <div className={`w-12 h-12 rounded-xl bg-momo-bg flex items-center justify-center flex-shrink-0`}>
                  <Icon className={`w-6 h-6 ${profile.color}`} />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-text-primary">{text.title}</span>
                    {isRecommended && (
                      <span className="text-xs px-2 py-0.5 rounded-full bg-accent-green/20 text-accent-green">
                        ✓
                      </span>
                    )}
                  </div>
                  <p className="text-sm text-text-secondary mt-1">{text.desc}</p>
                  <p className={`text-xs mt-2 ${profile.id === 'aggressive' ? 'text-accent-orange' : 'text-text-muted'}`}>
                    {text.tip}
                  </p>

                  {/* Features */}
                  <div className="flex gap-4 mt-3 text-xs">
                    <Feature enabled={profile.features.wardriving} label={t.wardriving} />
                    <Feature enabled={profile.features.scanning} label={t.scanning} />
                    <Feature 
                      enabled={profile.features.attacks} 
                      label={t.attacks}
                      highlight={profile.id === 'balanced'}
                    />
                  </div>
                </div>
                <div className={`w-6 h-6 rounded-full border-2 flex items-center justify-center flex-shrink-0 ${
                  isSelected ? 'bg-accent-green border-accent-green' : 'border-border-default'
                }`}>
                  {isSelected && (
                    <Check className="w-4 h-4 text-momo-bg" />
                  )}
                </div>
              </div>
            </button>
          )
        })}
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

function Feature({ enabled, label, highlight }: { enabled: boolean; label: string; highlight?: boolean }) {
  return (
    <span className={`flex items-center gap-1 ${enabled ? highlight ? 'text-accent-green' : 'text-text-primary' : 'text-text-muted'}`}>
      {enabled ? <Check className="w-3 h-3" /> : <X className="w-3 h-3" />}
      {label}
    </span>
  )
}

