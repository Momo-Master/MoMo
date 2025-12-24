import { useState } from 'react'
import { Lock, Eye, EyeOff, Check, X, ArrowRight, ArrowLeft } from 'lucide-react'
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
    title: 'Create Password',
    subtitle: 'This password protects your MoMo dashboard',
    password: 'Password',
    confirm: 'Confirm Password',
    strength: 'Password Strength',
    weak: 'Weak',
    fair: 'Fair',
    good: 'Good',
    strong: 'Strong',
    req8char: 'At least 8 characters',
    reqUpper: 'Contains uppercase',
    reqNumber: 'Contains numbers',
    reqMatch: 'Passwords match',
    back: 'Back',
    next: 'Next',
    error: 'Passwords do not match',
  },
  tr: {
    title: 'Şifre Oluştur',
    subtitle: 'Bu şifre MoMo panelini korur',
    password: 'Şifre',
    confirm: 'Şifre Tekrar',
    strength: 'Şifre Gücü',
    weak: 'Zayıf',
    fair: 'Orta',
    good: 'İyi',
    strong: 'Güçlü',
    req8char: 'En az 8 karakter',
    reqUpper: 'Büyük harf içerir',
    reqNumber: 'Rakam içerir',
    reqMatch: 'Şifreler eşleşiyor',
    back: 'Geri',
    next: 'İleri',
    error: 'Şifreler eşleşmiyor',
  },
}

export function Password({ data, updateData, goNext, goBack, loading, setLoading }: Props) {
  const t = T[data.language]
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState('')

  // Password requirements
  const has8Chars = password.length >= 8
  const hasUpper = /[A-Z]/.test(password)
  const hasNumber = /\d/.test(password)
  const passwordsMatch = password === confirm && password.length > 0

  // Strength calculation
  const getStrength = () => {
    let score = 0
    if (has8Chars) score++
    if (hasUpper) score++
    if (hasNumber) score++
    if (/[!@#$%^&*]/.test(password)) score++
    return score
  }

  const strength = getStrength()
  const strengthLabel = strength <= 1 ? t.weak : strength === 2 ? t.fair : strength === 3 ? t.good : t.strong
  const strengthClass = strength <= 1 ? 'strength-weak' : strength === 2 ? 'strength-fair' : strength === 3 ? 'strength-good' : 'strength-strong'

  const canProceed = has8Chars && passwordsMatch

  const handleNext = async () => {
    if (!canProceed) return
    
    setError('')
    setLoading(true)

    try {
      const res = await fetch('/api/step/password', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ password, confirm_password: confirm }),
      })

      if (!res.ok) {
        const data = await res.json()
        setError(data.detail || t.error)
        setLoading(false)
        return
      }

      updateData({ password })
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
      <div className="mb-8">
        <div className="w-14 h-14 rounded-2xl bg-accent-green/10 flex items-center justify-center mb-4">
          <Lock className="w-7 h-7 text-accent-green" />
        </div>
        <h1 className="text-2xl font-bold text-text-primary">{t.title}</h1>
        <p className="text-text-secondary mt-1">{t.subtitle}</p>
      </div>

      {/* Form */}
      <div className="flex-1 space-y-4">
        <div className="input-group">
          <label className="input-label">{t.password}</label>
          <div className="input-with-icon">
            <Lock className="input-icon w-5 h-5" />
            <input
              type={showPassword ? 'text' : 'password'}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="input pr-12"
              placeholder="••••••••"
              autoComplete="new-password"
            />
            <button
              type="button"
              onClick={() => setShowPassword(!showPassword)}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-text-muted hover:text-text-primary"
            >
              {showPassword ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
            </button>
          </div>

          {/* Strength Bar */}
          {password.length > 0 && (
            <div className="mt-3">
              <div className="flex justify-between text-xs mb-1">
                <span className="text-text-muted">{t.strength}</span>
                <span className={strength >= 3 ? 'text-accent-green' : 'text-text-muted'}>{strengthLabel}</span>
              </div>
              <div className="password-strength">
                <div className={`password-strength-bar ${strengthClass}`} />
              </div>
            </div>
          )}
        </div>

        <div className="input-group">
          <label className="input-label">{t.confirm}</label>
          <div className="input-with-icon">
            <Lock className="input-icon w-5 h-5" />
            <input
              type={showPassword ? 'text' : 'password'}
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              className="input"
              placeholder="••••••••"
              autoComplete="new-password"
            />
          </div>
        </div>

        {/* Requirements */}
        <div className="card bg-momo-bg/50 mt-6">
          <div className="space-y-2">
            <Requirement met={has8Chars} label={t.req8char} />
            <Requirement met={hasUpper} label={t.reqUpper} />
            <Requirement met={hasNumber} label={t.reqNumber} />
            <Requirement met={passwordsMatch} label={t.reqMatch} />
          </div>
        </div>

        {error && (
          <div className="input-error text-center">{error}</div>
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
          disabled={!canProceed || loading}
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

function Requirement({ met, label }: { met: boolean; label: string }) {
  return (
    <div className={`flex items-center gap-2 text-sm ${met ? 'text-accent-green' : 'text-text-muted'}`}>
      {met ? <Check className="w-4 h-4" /> : <X className="w-4 h-4" />}
      {label}
    </div>
  )
}

