import type { Metadata } from "next";
import "./globals.css";
import { Header, Footer } from "@/components/site";
export const metadata: Metadata={title:{default:"TutorPlan",template:"%s | TutorPlan"},description:"지역별 학습관리와 과외 정보를 안내합니다."};
export default function Layout({children}:{children:React.ReactNode}){return <html lang="ko"><body><Header/><main className="main"><div className="shell">{children}</div></main><Footer/></body></html>}
