import { useState, useEffect } from 'react'
import { Welcome } from './pages/Welcome'
import { Password } from './pages/Password'
import { Network } from './pages/Network'
import { Profile } from './pages/Profile'
import { Nexus } from './pages/Nexus'
import { Summary } from './pages/Summary'
import { Complete } from './pages/Complete'

export type WizardStep = 'welcome' | 'password' | 'network' | 'profile' | 'nexus' | 'summary' | 'complete'

export interface WizardData {
  language: 'en' | 'tr'
  password: string
  network: {
    mode: 'ap' | 'client'
    ap_ssid: string
    ap_password: string
    ap_channel: number
    client_ssid: string
    client_password: string
  }
  profile: 'passive' | 'balanced' | 'aggressive'
  nexus: {
    enabled: boolean
    url: string
    device_name: string
  }
}

const initialData: WizardData = {
  language: 'en',
  password: '',
  network: {
    mode: 'ap',
    ap_ssid: 'MoMo-Management',
    ap_password: '',
    ap_channel: 6,
    client_ssid: '',
    client_password: '',
  },
  profile: 'balanced',
  nexus: {
    enabled: false,
    url: '',
    device_name: 'MoMo-Field-01',
  },
}

const STEPS: WizardStep[] = ['welcome', 'password', 'network', 'profile', 'nexus', 'summary', 'complete']

function App() {
  const [step, setStep] = useState<WizardStep>('welcome')
  const [data, setData] = useState<WizardData>(initialData)
  const [loading, setLoading] = useState(false)

  // Fetch initial status
  useEffect(() => {
    fetch('/api/status')
      .then(res => res.json())
      .then(status => {
        if (status.current_step && status.current_step !== 'welcome') {
          setStep(status.current_step as WizardStep)
        }
      })
      .catch(() => {
        // API not available, continue with welcome
      })
  }, [])

  const currentStepIndex = STEPS.indexOf(step)

  const goNext = () => {
    const nextIndex = currentStepIndex + 1
    if (nextIndex < STEPS.length) {
      setStep(STEPS[nextIndex])
    }
  }

  const goBack = () => {
    const prevIndex = currentStepIndex - 1
    if (prevIndex >= 0) {
      setStep(STEPS[prevIndex])
    }
  }

  const updateData = (updates: Partial<WizardData>) => {
    setData(prev => ({ ...prev, ...updates }))
  }

  const renderStep = () => {
    const props = { data, updateData, goNext, goBack, loading, setLoading }
    
    switch (step) {
      case 'welcome':
        return <Welcome {...props} />
      case 'password':
        return <Password {...props} />
      case 'network':
        return <Network {...props} />
      case 'profile':
        return <Profile {...props} />
      case 'nexus':
        return <Nexus {...props} />
      case 'summary':
        return <Summary {...props} />
      case 'complete':
        return <Complete {...props} />
      default:
        return <Welcome {...props} />
    }
  }

  return (
    <div className="wizard-container">
      {/* Progress Indicator */}
      {step !== 'welcome' && step !== 'complete' && (
        <div className="progress-bar">
          {STEPS.slice(1, -1).map((s, i) => (
            <div
              key={s}
              className={`progress-dot ${
                i < currentStepIndex - 1 ? 'completed' :
                i === currentStepIndex - 1 ? 'active' : ''
              }`}
            />
          ))}
        </div>
      )}

      {/* Step Content */}
      <div className="flex-1 animate-slide-up" key={step}>
        {renderStep()}
      </div>
    </div>
  )
}

export default App

