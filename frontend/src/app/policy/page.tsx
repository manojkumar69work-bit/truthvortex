import Link from "next/link";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Content Policy & Terms",
  description:
    "Red4ce editorial rules, content ownership, and terms of use: what is ours, how we credit other publishers, and what readers may do with our work.",
  alternates: { canonical: "/policy" },
};

const EFFECTIVE = "27 October 2026";
const contactEmail = process.env.NEXT_PUBLIC_CONTACT_EMAIL;

function Contact() {
  return contactEmail ? (
    <a href={`mailto:${contactEmail}`} className="font-bold text-red-600 underline">
      {contactEmail}
    </a>
  ) : (
    <span className="font-bold">the Red4ce editor</span>
  );
}

function Section({
  id,
  title,
  children,
}: {
  id: string;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section id={id} className="scroll-mt-6 border-t border-slate-200 pt-8">
      <h2 className="text-2xl font-black tracking-tight text-slate-900">{title}</h2>
      <div className="mt-4 space-y-4 text-[16px] leading-7 text-slate-700">{children}</div>
    </section>
  );
}

export default function PolicyPage() {
  return (
    <main className="min-h-screen bg-white px-4 py-10 text-slate-900">
      <article className="mx-auto max-w-3xl space-y-10">
        <header>
          <Link href="/" className="text-3xl font-black tracking-tight">
            <span className="text-red-600">Red</span>4ce
          </Link>
          <h1 className="mt-6 text-4xl font-black tracking-tight">Content Policy &amp; Terms</h1>
          <p className="mt-3 text-slate-500">Effective {EFFECTIVE}</p>
          <p className="mt-6 text-lg leading-8 text-slate-700">
            One rule runs through this page: <strong>everything Red4ce publishes as its own is
            ours</strong>. We write it, we photograph it, or we hold written rights to it. When we
            show news first reported by someone else, we say so and link to them.
          </p>
          <nav aria-label="On this page" className="mt-6 flex flex-wrap gap-2 text-sm font-bold">
            {[
              ["editorial", "Editorial rules"],
              ["ownership", "What we own"],
              ["sources", "Other publishers"],
              ["use", "Using our content"],
              ["privacy", "Privacy & analytics"],
              ["takedown", "Corrections & takedowns"],
            ].map(([id, label]) => (
              <a
                key={id}
                href={`#${id}`}
                className="rounded-full border border-slate-300 px-3 py-1 text-slate-600 hover:border-red-600 hover:text-red-600"
              >
                {label}
              </a>
            ))}
          </nav>
        </header>

        <Section id="editorial" title="1. Editorial rules for our newsroom">
          <p>
            These rules bind every person who writes or uploads through the Red4ce newsroom. The
            newsroom will not publish an article until the writer confirms them.
          </p>
          <ol className="list-decimal space-y-3 pl-6">
            <li>
              <strong>Original words only.</strong> Write every article yourself. Do not copy,
              translate word-for-word, or lightly reword text from another newspaper, channel,
              website, or social media post.
            </li>
            <li>
              <strong>Our photos only.</strong> Upload only photos and graphics a Red4ce team
              member made, or ones we hold written permission or a paid licence for. Never use an
              image found on Google, another news site, or social media. The newsroom refuses
              links to outside images; every photo must be uploaded to our own store.
            </li>
            <li>
              <strong>Facts before speed.</strong> Confirm facts with at least one named or
              documented source before publishing. Mark anything unconfirmed as unconfirmed.
            </li>
            <li>
              <strong>Credit what we did not report.</strong> If a fact first came from another
              outlet, say so in the article.
            </li>
            <li>
              <strong>Protect people.</strong> Do not name or show victims of sexual offences,
              minors in crime stories, or anyone whose identity the law protects. Do not publish
              private phone numbers, addresses, or ID documents.
            </li>
            <li>
              <strong>No hate, no defamation.</strong> Do not publish content that attacks people
              for religion, caste, gender, or community, or claims we cannot back up about a named
              person.
            </li>
            <li>
              <strong>Fix mistakes openly.</strong> Correct errors in the article as soon as they
              are found, and note the correction.
            </li>
          </ol>
          <p>
            An article that breaks these rules is hidden or deleted from the newsroom, and every
            change is recorded in the newsroom&apos;s security log.
          </p>
        </Section>

        <Section id="ownership" title="2. What Red4ce owns">
          <p>The following belong to Red4ce. All rights are reserved.</p>
          <ul className="list-disc space-y-2 pl-6">
            <li>The Red4ce name, logo, and the look of this website.</li>
            <li>Articles marked <strong>Red4ce Original</strong>, and the photos in them.</li>
            <li>The Telugu summaries and headlines Red4ce writes for news from other sources.</li>
            <li>The software, design, and layout of the site.</li>
          </ul>
        </Section>

        <Section id="sources" title="3. News first reported by other publishers">
          <p>
            Some items on Red4ce are short Telugu summaries of news first reported by other
            publishers. For those items the original reporting, text, and photos stay the
            property of that publisher. Red4ce does not claim them.
          </p>
          <p>
            Each such item names its publisher and links to the original article so readers can
            read it in full. We do not republish full articles from other publishers.
          </p>
        </Section>

        <Section id="use" title="4. Using Red4ce content">
          <p>You may read Red4ce, and share links to our pages. Without written permission from Red4ce you may not:</p>
          <ul className="list-disc space-y-2 pl-6">
            <li>Copy or republish our articles, summaries, or photos, in whole or in part.</li>
            <li>Scrape, crawl in bulk, or download the site or its API.</li>
            <li>Use our content to train or feed AI systems.</li>
            <li>Show our pages inside another website (framing).</li>
            <li>Remove or hide the Red4ce name from anything you share.</li>
          </ul>
          <p>
            Short quotes with a clear credit and a link back to the Red4ce page are allowed for news
            reporting, criticism, and review.
          </p>
        </Section>

        <Section id="privacy" title="5. Privacy and analytics">
          <p>
            Red4ce counts visits to improve the site. We do not use cookies or advertising
            trackers. We store which page or article was viewed, the type of device, and the
            website that sent the visitor. Visitors are counted with a one-way code that changes
            every day, so we cannot follow a person from one day to the next. We delete visit
            records after 90 days.
          </p>
        </Section>

        <Section id="takedown" title="6. Corrections, complaints, and takedowns">
          <p>
            If you think something on Red4ce is wrong, or that we used your work without
            permission, contact <Contact />. Tell us the page link and what is wrong. We review
            every request and remove material that breaks this policy.
          </p>
        </Section>

        <footer className="border-t border-slate-200 pt-6 text-sm text-slate-500">
          © {new Date().getFullYear()} Red4ce. All rights reserved. ·{" "}
          <Link href="/" className="font-bold text-red-600">
            Back to the news
          </Link>
        </footer>
      </article>
    </main>
  );
}
