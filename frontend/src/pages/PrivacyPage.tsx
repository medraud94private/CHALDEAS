/**
 * PrivacyPage - Privacy Policy
 */
import { useTranslation } from 'react-i18next'
import './LegalPage.css'

interface Props {
  onClose: () => void
}

export function PrivacyPage({ onClose }: Props) {
  const { t, i18n } = useTranslation()
  const lang = i18n.language

  return (
    <div className="legal-overlay" onClick={onClose} role="presentation">
      <div
        className="legal-page"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-labelledby="privacy-title"
      >
        <div className="legal-header">
          <h1 id="privacy-title">{t('legal.privacy.title', 'Privacy Policy')}</h1>
          <button className="legal-close" onClick={onClose} aria-label="Close privacy policy">✕</button>
        </div>

        <div className="legal-content">
          {lang === 'ko' ? (
            <>
              <p className="legal-updated">최종 수정일: 2026년 1월 28일</p>

              <section>
                <h2>1. 개요</h2>
                <p>
                  CHALDEAS는 사용자의 개인정보 보호를 중요시합니다.
                  본 개인정보처리방침은 서비스 이용 시 수집되는 정보와 그 처리 방법을 설명합니다.
                </p>
              </section>

              <section>
                <h2>2. 수집하는 정보</h2>
                <h3>자동으로 수집되는 정보</h3>
                <ul>
                  <li>브라우저 유형 및 버전</li>
                  <li>운영체제</li>
                  <li>접속 시간</li>
                  <li>참조 URL</li>
                </ul>
                <p>
                  <strong>참고:</strong> 본 서비스는 회원가입이 없으며, 개인을 식별할 수 있는
                  정보(이름, 이메일 등)를 수집하지 않습니다.
                </p>

                <h3>로컬 저장소 (localStorage)</h3>
                <p>다음 정보가 브라우저에 로컬로 저장됩니다:</p>
                <ul>
                  <li>언어 설정</li>
                  <li>화면 표시 설정</li>
                  <li>북마크한 이벤트</li>
                </ul>
                <p>이 데이터는 서버로 전송되지 않으며, 브라우저 설정에서 삭제할 수 있습니다.</p>
              </section>

              <section>
                <h2>3. 정보의 이용</h2>
                <p>수집된 정보는 다음 목적으로만 사용됩니다:</p>
                <ul>
                  <li>서비스 제공 및 운영</li>
                  <li>서비스 개선을 위한 통계 분석</li>
                  <li>서비스 오류 진단 및 해결</li>
                </ul>
              </section>

              <section>
                <h2>4. 제3자 서비스</h2>
                <p>본 서비스는 다음 외부 서비스를 사용합니다:</p>
                <ul>
                  <li><strong>Wikipedia/Wikidata</strong>: 역사 데이터 제공</li>
                  <li><strong>Google Fonts</strong>: 폰트 제공</li>
                </ul>
                <p>각 서비스의 개인정보처리방침을 참조하시기 바랍니다.</p>
              </section>

              <section>
                <h2>5. 데이터 보안</h2>
                <p>
                  본 서비스는 HTTPS를 통해 암호화된 연결을 제공합니다.
                  그러나 인터넷을 통한 데이터 전송의 완전한 보안을 보장할 수 없습니다.
                </p>
              </section>

              <section>
                <h2>6. 아동 개인정보</h2>
                <p>
                  본 서비스는 만 14세 미만 아동의 개인정보를 의도적으로 수집하지 않습니다.
                </p>
              </section>

              <section>
                <h2>7. 변경 사항</h2>
                <p>
                  본 개인정보처리방침은 필요 시 변경될 수 있으며, 변경 시 서비스 내 공지합니다.
                </p>
              </section>

              <section>
                <h2>8. 문의</h2>
                <p>
                  개인정보 관련 문의: <a href="https://github.com/anthropics/claude-code/issues">GitHub Issues</a>
                </p>
              </section>
            </>
          ) : lang === 'ja' ? (
            <>
              <p className="legal-updated">最終更新日: 2026年1月28日</p>

              <section>
                <h2>1. 概要</h2>
                <p>
                  CHALDEASはユーザーのプライバシー保護を重視しています。
                  本プライバシーポリシーは、サービス利用時に収集される情報とその処理方法について説明します。
                </p>
              </section>

              <section>
                <h2>2. 収集する情報</h2>
                <h3>自動的に収集される情報</h3>
                <ul>
                  <li>ブラウザの種類とバージョン</li>
                  <li>オペレーティングシステム</li>
                  <li>アクセス時間</li>
                  <li>参照URL</li>
                </ul>
                <p>
                  <strong>注意:</strong> 本サービスは会員登録がなく、個人を特定できる情報
                  （名前、メールアドレスなど）を収集しません。
                </p>

                <h3>ローカルストレージ</h3>
                <p>以下の情報がブラウザにローカルで保存されます：</p>
                <ul>
                  <li>言語設定</li>
                  <li>表示設定</li>
                  <li>ブックマークしたイベント</li>
                </ul>
              </section>

              <section>
                <h2>3. 情報の利用</h2>
                <p>収集された情報は以下の目的でのみ使用されます：</p>
                <ul>
                  <li>サービスの提供と運営</li>
                  <li>サービス改善のための統計分析</li>
                  <li>サービスエラーの診断と解決</li>
                </ul>
              </section>

              <section>
                <h2>4. お問い合わせ</h2>
                <p>
                  プライバシーに関するお問い合わせ: <a href="https://github.com/anthropics/claude-code/issues">GitHub Issues</a>
                </p>
              </section>
            </>
          ) : (
            <>
              <p className="legal-updated">Last updated: January 28, 2026</p>

              <section>
                <h2>1. Overview</h2>
                <p>
                  CHALDEAS values the protection of user privacy.
                  This Privacy Policy explains what information is collected when you use the service
                  and how it is processed.
                </p>
              </section>

              <section>
                <h2>2. Information We Collect</h2>
                <h3>Automatically Collected Information</h3>
                <ul>
                  <li>Browser type and version</li>
                  <li>Operating system</li>
                  <li>Access time</li>
                  <li>Referral URL</li>
                </ul>
                <p>
                  <strong>Note:</strong> This service does not have user registration and does not
                  collect personally identifiable information (name, email, etc.).
                </p>

                <h3>Local Storage</h3>
                <p>The following information is stored locally in your browser:</p>
                <ul>
                  <li>Language preferences</li>
                  <li>Display settings</li>
                  <li>Bookmarked events</li>
                </ul>
                <p>This data is not sent to the server and can be deleted through browser settings.</p>
              </section>

              <section>
                <h2>3. Use of Information</h2>
                <p>The collected information is used only for the following purposes:</p>
                <ul>
                  <li>Providing and operating the service</li>
                  <li>Statistical analysis for service improvement</li>
                  <li>Diagnosing and resolving service errors</li>
                </ul>
              </section>

              <section>
                <h2>4. Third-Party Services</h2>
                <p>This service uses the following external services:</p>
                <ul>
                  <li><strong>Wikipedia/Wikidata</strong>: Historical data source</li>
                  <li><strong>Google Fonts</strong>: Font delivery</li>
                </ul>
                <p>Please refer to each service's privacy policy.</p>
              </section>

              <section>
                <h2>5. Data Security</h2>
                <p>
                  This service provides encrypted connections through HTTPS.
                  However, we cannot guarantee complete security of data transmission over the Internet.
                </p>
              </section>

              <section>
                <h2>6. Children's Privacy</h2>
                <p>
                  This service does not intentionally collect personal information from children under 14.
                </p>
              </section>

              <section>
                <h2>7. Changes</h2>
                <p>
                  This Privacy Policy may be changed as needed, and changes will be announced within the service.
                </p>
              </section>

              <section>
                <h2>8. Contact</h2>
                <p>
                  Privacy inquiries: <a href="https://github.com/anthropics/claude-code/issues">GitHub Issues</a>
                </p>
              </section>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
