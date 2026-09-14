import Link from "next/link";
export function Header(){return <header className="header"><div className="shell"><Link className="brand" href="/">TutorPlan</Link><nav className="nav"><Link href="/regions">지역 찾기</Link><Link href="/tutoring">학습관리</Link><Link href="/contact">문의</Link></nav></div></header>}
export function Footer(){return <footer className="footer"><div className="shell">TutorPlan · <Link href="/privacy">개인정보처리방침</Link> · <Link href="/terms">이용약관</Link></div></footer>}
export function ContactCTA(){return <aside className="cta"><strong>학습 상황을 차분히 정리해 보세요.</strong><p>문의 전 현재 학습 흐름과 변화 기준을 기록해 두면 상담에 도움이 됩니다.</p><Link href="/contact">문의 안내 보기</Link></aside>}
