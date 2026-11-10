import { Kicker, Reveal } from "./ui";

const points = [
  {
    title: "The original sentence stays",
    body: "Cleaning does not overwrite the feedback that arrived. The source text remains the record.",
  },
  {
    title: "PII is redacted on the cleaned copy",
    body: "When personal data is detected, it is replaced on the cleaned text. The inspection reports the types that were found.",
  },
  {
    title: "Quality flags mark the record",
    body: "Quality status, scores, and flags describe what the pipeline noticed. A negative comment is not treated as a low-quality record.",
  },
];

export function Security() {
  return (
    <section className="border-t border-line bg-paper-deep">
      <div className="mx-auto max-w-[1180px] px-5 py-24">
        <Reveal>
          <Kicker>Data handling</Kicker>
          <h2 className="section-title mt-4 max-w-[16ch]">What the pipeline actually protects.</h2>
          <p className="mt-5 max-w-xl text-[16px] leading-relaxed text-ink-soft">
            These are the data-quality behaviors implemented today. They are not a certification, an audit, or an
            enterprise security guarantee.
          </p>
        </Reveal>
        <div className="mt-14 grid gap-8 md:grid-cols-3">
          {points.map((point, index) => (
            <Reveal key={point.title} delay={index * 0.05}>
              <p className="text-[12px] tracking-[0.16em] text-mute">0{index + 1}</p>
              <h3 className="mt-3 text-[20px] tracking-[-0.03em]">{point.title}</h3>
              <p className="mt-3 text-[15px] leading-relaxed text-ink-soft">{point.body}</p>
            </Reveal>
          ))}
        </div>
      </div>
    </section>
  );
}
