import Link from "next/link";

import { Footer } from "@/components/landing/footer";
import { Header } from "@/components/landing/header";
import { getLocaleByLang } from "@/core/i18n/locale";

const LICENSE_TEXT = `MIT License

Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
Copyright (c) 2025-2026 UniDeer Authors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.`;

export default async function LicensePage({
  params,
}: {
  params: Promise<{ lang: string }>;
}) {
  const { lang } = await params;
  const locale = getLocaleByLang(lang);
  return (
    <div className="min-h-screen w-full overflow-x-clip bg-[#0a0a0a]">
      <Header locale={locale} />
      <main className="container-md mx-auto flex max-w-3xl flex-col items-center px-4 pt-28 pb-16">
        <h1 className="font-serif text-3xl md:text-4xl">License</h1>
        <p className="text-muted-foreground mt-4 text-center text-sm leading-relaxed">
          UniDeer is a fork of{" "}
          <Link
            href="https://github.com/bytedance/deer-flow"
            target="_blank"
            rel="noopener noreferrer"
            className="text-foreground underline underline-offset-4 hover:opacity-80"
          >
            DeerFlow
          </Link>
          , originally created by Bytedance Ltd. and released under the MIT
          License. The original copyright and permission notice are preserved
          below.
        </p>
        <pre className="text-muted-foreground mt-10 w-full overflow-x-auto whitespace-pre-wrap rounded-md border border-border/40 bg-background/40 p-6 font-mono text-xs leading-relaxed">
          {LICENSE_TEXT}
        </pre>
      </main>
      <Footer locale={locale} />
    </div>
  );
}
