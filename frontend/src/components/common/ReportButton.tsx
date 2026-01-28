/**
 * ReportButton - Content quality report button
 * Allows users to report incorrect, suspicious, or low-quality content.
 */
import { useState } from 'react'
import { api } from '../../api/client'
import './ReportButton.css'

type EntityType = 'person' | 'event' | 'location' | 'source'
type ReportType = 'incorrect' | 'suspicious' | 'low_quality' | 'inappropriate' | 'other'

interface Props {
  entityType: EntityType
  entityId: number | string
  fieldName?: string
  className?: string
}

interface ReportFormData {
  report_type: ReportType
  reason: string
  suggested_correction?: string
}

const REPORT_TYPES: { value: ReportType; label: string; desc: string }[] = [
  { value: 'incorrect', label: 'Incorrect', desc: 'Factually wrong information' },
  { value: 'suspicious', label: 'Suspicious', desc: 'Possibly AI-generated or unverified' },
  { value: 'low_quality', label: 'Low Quality', desc: 'Poor grammar, formatting, or content' },
  { value: 'inappropriate', label: 'Inappropriate', desc: 'Offensive or inappropriate content' },
  { value: 'other', label: 'Other', desc: 'Other issue not listed above' },
]

export function ReportButton({ entityType, entityId, fieldName, className }: Props) {
  const [isOpen, setIsOpen] = useState(false)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [submitted, setSubmitted] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [formData, setFormData] = useState<ReportFormData>({
    report_type: 'incorrect',
    reason: '',
  })

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (formData.reason.length < 10) {
      setError('Please provide more details (at least 10 characters)')
      return
    }

    setIsSubmitting(true)
    setError(null)

    try {
      await api.post('/reports/', {
        entity_type: entityType,
        entity_id: typeof entityId === 'string' ? parseInt(entityId, 10) : entityId,
        field_name: fieldName,
        report_type: formData.report_type,
        reason: formData.reason,
        suggested_correction: formData.suggested_correction || undefined,
      })
      setSubmitted(true)
      setTimeout(() => {
        setIsOpen(false)
        setSubmitted(false)
        setFormData({ report_type: 'incorrect', reason: '' })
      }, 2000)
    } catch (err: unknown) {
      const axiosError = err as { response?: { status: number; data?: { detail?: string } } }
      if (axiosError.response?.status === 429) {
        setError('Too many reports. Please try again later.')
      } else if (axiosError.response?.status === 409) {
        setError('You already have a pending report for this content.')
      } else {
        setError('Failed to submit report. Please try again.')
      }
    } finally {
      setIsSubmitting(false)
    }
  }

  const handleClose = () => {
    if (!isSubmitting) {
      setIsOpen(false)
      setError(null)
    }
  }

  return (
    <>
      <button
        className={`report-btn ${className || ''}`}
        onClick={() => setIsOpen(true)}
        title="Report content issue"
      >
        <span className="report-btn-icon">⚑</span>
      </button>

      {isOpen && (
        <div className="report-modal-overlay" onClick={handleClose}>
          <div className="report-modal" onClick={(e) => e.stopPropagation()}>
            <div className="report-modal-header">
              <h3>Report Issue</h3>
              <button className="report-close" onClick={handleClose}>✕</button>
            </div>

            {submitted ? (
              <div className="report-success">
                <span className="success-icon">✓</span>
                <p>Report submitted. Thank you for your feedback!</p>
              </div>
            ) : (
              <form onSubmit={handleSubmit} className="report-form">
                <div className="report-field">
                  <label>Issue Type</label>
                  <div className="report-type-list">
                    {REPORT_TYPES.map((type) => (
                      <label
                        key={type.value}
                        className={`report-type-option ${formData.report_type === type.value ? 'selected' : ''}`}
                      >
                        <input
                          type="radio"
                          name="report_type"
                          value={type.value}
                          checked={formData.report_type === type.value}
                          onChange={(e) => setFormData({ ...formData, report_type: e.target.value as ReportType })}
                        />
                        <span className="type-label">{type.label}</span>
                        <span className="type-desc">{type.desc}</span>
                      </label>
                    ))}
                  </div>
                </div>

                <div className="report-field">
                  <label htmlFor="reason">Description *</label>
                  <textarea
                    id="reason"
                    value={formData.reason}
                    onChange={(e) => setFormData({ ...formData, reason: e.target.value })}
                    placeholder="Please describe the issue in detail..."
                    rows={4}
                    maxLength={2000}
                    required
                  />
                  <span className="char-count">{formData.reason.length}/2000</span>
                </div>

                <div className="report-field">
                  <label htmlFor="correction">Suggested Correction (optional)</label>
                  <textarea
                    id="correction"
                    value={formData.suggested_correction || ''}
                    onChange={(e) => setFormData({ ...formData, suggested_correction: e.target.value })}
                    placeholder="If you know the correct information, please share..."
                    rows={2}
                    maxLength={2000}
                  />
                </div>

                {error && <div className="report-error">{error}</div>}

                <div className="report-actions">
                  <button type="button" className="report-cancel" onClick={handleClose} disabled={isSubmitting}>
                    Cancel
                  </button>
                  <button type="submit" className="report-submit" disabled={isSubmitting}>
                    {isSubmitting ? 'Submitting...' : 'Submit Report'}
                  </button>
                </div>
              </form>
            )}
          </div>
        </div>
      )}
    </>
  )
}
