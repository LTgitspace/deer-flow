import Link from "next/link";

import { DEFAULT_LOCALE, type Locale } from "@/core/i18n/locale";
import { getI18n } from "@/core/i18n/server";
import { cn } from "@/lib/utils";

export type FooterProps = {
  className?: string;
  locale?: Locale;
};

export async function Footer({ className, locale }: FooterProps) {
  const year = new Date().getFullYear();
  const { locale: resolvedLocale } = await getI18n(locale ?? DEFAULT_LOCALE);
  const lang = resolvedLocale.substring(0, 2);
  return (
    <footer
      className={cn(
        "container-md mx-auto mt-32 flex flex-col items-center justify-center",
        className,
      )}
    >
      <hr className="from-border/0 to-border/0 m-0 h-px w-full border-none bg-linear-to-r via-white/20" />
      <div className="text-muted-foreground container flex h-20 flex-col items-center justify-center text-sm">
        <p className="text-center font-serif text-lg md:text-xl">
          &quot;Originated from Open Source, give back to Open Source.&quot;
        </p>
      </div>
      <div className="text-muted-foreground container mb-8 flex flex-col items-center justify-center text-xs">
        <p>UniDeer, a fork of DeerFlow</p>
        <Link href={`/${lang}/license`} className="hover:text-foreground transition-colors">
          Licensed under MIT License
        </Link>
        <p>&copy; {year} UniDeer</p>
      </div>
    </footer>
  );
}
