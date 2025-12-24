import { Globe } from 'lucide-react'
import type { WizardData } from '../App'

interface Props {
  data: WizardData
  updateData: (updates: Partial<WizardData>) => void
  goNext: () => void
}

export function Welcome({ data, updateData, goNext }: Props) {
  const handleLanguageSelect = async (lang: 'en' | 'tr') => {
    updateData({ language: lang })
    
    try {
      await fetch('/api/step/language', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ language: lang }),
      })
    } catch {
      // Continue even if API fails
    }
    
    goNext()
  }

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="wizard-header mt-12">
        <div className="wizard-logo">🔥</div>
        <h1 className="wizard-title">Welcome to MoMo</h1>
        <p className="wizard-subtitle">Modular Offensive Mobile Operations</p>
      </div>

      {/* Language Selection */}
      <div className="flex-1 flex flex-col justify-center space-y-4">
        <p className="text-center text-text-secondary mb-4">
          <Globe className="inline-block w-4 h-4 mr-2" />
          Select your language / Dil seçin
        </p>

        <button
          onClick={() => handleLanguageSelect('en')}
          className={`option-card ${data.language === 'en' ? 'selected' : ''}`}
        >
          <div className="option-icon">🇬🇧</div>
          <div className="option-content">
            <div className="option-title">English</div>
            <div className="option-desc">Continue in English</div>
          </div>
          <div className="option-check">
            {data.language === 'en' && (
              <svg className="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
              </svg>
            )}
          </div>
        </button>

        <button
          onClick={() => handleLanguageSelect('tr')}
          className={`option-card ${data.language === 'tr' ? 'selected' : ''}`}
        >
          <div className="option-icon">🇹🇷</div>
          <div className="option-content">
            <div className="option-title">Türkçe</div>
            <div className="option-desc">Türkçe devam et</div>
          </div>
          <div className="option-check">
            {data.language === 'tr' && (
              <svg className="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
              </svg>
            )}
          </div>
        </button>
      </div>

      {/* Version */}
      <div className="text-center text-text-muted text-xs mt-8">
        MoMo v1.6.0 • First Boot Wizard
      </div>
    </div>
  )
}

