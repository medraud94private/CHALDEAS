/**
 * TermsPage - Terms of Service
 */
import { useTranslation } from 'react-i18next'
import './LegalPage.css'

interface Props {
  onClose: () => void
}

export function TermsPage({ onClose }: Props) {
  const { t, i18n } = useTranslation()
  const lang = i18n.language

  return (
    <div className="legal-overlay" onClick={onClose} role="presentation">
      <div
        className="legal-page"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-labelledby="terms-title"
      >
        <div className="legal-header">
          <h1 id="terms-title">{t('legal.terms.title', 'Terms of Service')}</h1>
          <button className="legal-close" onClick={onClose} aria-label="Close terms of service">✕</button>
        </div>

        <div className="legal-content">
          {lang === 'ko' ? (
            <>
              <p className="legal-updated">최종 수정일: 2026년 1월 28일</p>

              <section>
                <h2>1. 서비스 소개</h2>
                <p>
                  CHALDEAS는 역사적 사건, 인물, 장소에 대한 정보를 3D 지구본 인터페이스로
                  제공하는 교육 목적의 웹 서비스입니다.
                </p>
              </section>

              <section>
                <h2>2. 서비스 이용</h2>
                <p>본 서비스는 누구나 무료로 이용할 수 있습니다. 단, 다음 행위는 금지됩니다:</p>
                <ul>
                  <li>서비스의 정상적인 운영을 방해하는 행위</li>
                  <li>자동화된 수단으로 대량의 데이터를 수집하는 행위</li>
                  <li>서비스를 상업적 목적으로 무단 이용하는 행위</li>
                  <li>타인의 권리를 침해하는 행위</li>
                </ul>
              </section>

              <section>
                <h2>3. 콘텐츠 및 저작권</h2>
                <p>
                  본 서비스의 역사 데이터 중 상당 부분은 Wikipedia에서 제공되며,
                  Creative Commons Attribution-ShareAlike 4.0 (CC BY-SA 4.0) 라이선스를 따릅니다.
                </p>
                <p>
                  각 콘텐츠의 출처는 상세 페이지에서 확인할 수 있습니다.
                </p>
              </section>

              <section>
                <h2>4. 면책 조항</h2>
                <p>
                  본 서비스는 교육 및 참고 목적으로만 제공됩니다.
                  역사적 정보의 정확성을 보장하지 않으며, 학술적 인용이나
                  중요한 의사결정에 본 서비스의 정보만을 의존해서는 안 됩니다.
                </p>
                <p>
                  서비스 이용으로 인해 발생하는 직접적 또는 간접적 손해에 대해
                  운영자는 책임을 지지 않습니다.
                </p>
              </section>

              <section>
                <h2>5. 서비스 변경 및 중단</h2>
                <p>
                  운영자는 필요에 따라 서비스의 전부 또는 일부를 수정, 변경,
                  중단할 수 있습니다.
                </p>
              </section>

              <section>
                <h2>6. 약관 변경</h2>
                <p>
                  본 약관은 필요 시 변경될 수 있으며, 변경 시 서비스 내 공지합니다.
                </p>
              </section>

              <section>
                <h2>7. 문의</h2>
                <p>
                  서비스 관련 문의: <a href="https://github.com/anthropics/claude-code/issues">GitHub Issues</a>
                </p>
              </section>
            </>
          ) : lang === 'ja' ? (
            <>
              <p className="legal-updated">最終更新日: 2026年1月28日</p>

              <section>
                <h2>1. サービス概要</h2>
                <p>
                  CHALDEASは、歴史的な出来事、人物、場所に関する情報を3D地球儀インターフェースで
                  提供する教育目的のWebサービスです。
                </p>
              </section>

              <section>
                <h2>2. サービス利用</h2>
                <p>本サービスは無料でご利用いただけます。ただし、以下の行為は禁止されています：</p>
                <ul>
                  <li>サービスの正常な運営を妨げる行為</li>
                  <li>自動化された手段で大量のデータを収集する行為</li>
                  <li>サービスを商業目的で無断利用する行為</li>
                  <li>他者の権利を侵害する行為</li>
                </ul>
              </section>

              <section>
                <h2>3. コンテンツと著作権</h2>
                <p>
                  本サービスの歴史データの多くはWikipediaから提供されており、
                  Creative Commons Attribution-ShareAlike 4.0 (CC BY-SA 4.0) ライセンスに従います。
                </p>
                <p>
                  各コンテンツの出典は詳細ページで確認できます。
                </p>
              </section>

              <section>
                <h2>4. 免責事項</h2>
                <p>
                  本サービスは教育および参考目的でのみ提供されます。
                  歴史情報の正確性を保証するものではなく、学術的引用や
                  重要な意思決定に本サービスの情報のみを依存すべきではありません。
                </p>
              </section>

              <section>
                <h2>5. お問い合わせ</h2>
                <p>
                  サービスに関するお問い合わせ: <a href="https://github.com/anthropics/claude-code/issues">GitHub Issues</a>
                </p>
              </section>
            </>
          ) : (
            <>
              <p className="legal-updated">Last updated: January 28, 2026</p>

              <section>
                <h2>1. Service Description</h2>
                <p>
                  CHALDEAS is an educational web service that provides information about
                  historical events, figures, and places through a 3D globe interface.
                </p>
              </section>

              <section>
                <h2>2. Use of Service</h2>
                <p>This service is free for everyone to use. However, the following activities are prohibited:</p>
                <ul>
                  <li>Interfering with the normal operation of the service</li>
                  <li>Collecting large amounts of data through automated means</li>
                  <li>Using the service for commercial purposes without permission</li>
                  <li>Infringing on the rights of others</li>
                </ul>
              </section>

              <section>
                <h2>3. Content and Copyright</h2>
                <p>
                  A significant portion of the historical data in this service is sourced from Wikipedia
                  and is licensed under Creative Commons Attribution-ShareAlike 4.0 (CC BY-SA 4.0).
                </p>
                <p>
                  The source of each piece of content can be found on the detail page.
                </p>
              </section>

              <section>
                <h2>4. Disclaimer</h2>
                <p>
                  This service is provided for educational and reference purposes only.
                  We do not guarantee the accuracy of historical information, and you should not
                  rely solely on information from this service for academic citations or
                  important decisions.
                </p>
                <p>
                  The operator is not responsible for any direct or indirect damages
                  arising from the use of this service.
                </p>
              </section>

              <section>
                <h2>5. Service Changes</h2>
                <p>
                  The operator may modify, change, or discontinue all or part of the service as needed.
                </p>
              </section>

              <section>
                <h2>6. Changes to Terms</h2>
                <p>
                  These terms may be changed as needed, and changes will be announced within the service.
                </p>
              </section>

              <section>
                <h2>7. Contact</h2>
                <p>
                  Service inquiries: <a href="https://github.com/anthropics/claude-code/issues">GitHub Issues</a>
                </p>
              </section>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
