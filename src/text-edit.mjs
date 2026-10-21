/**
 * Replace the changed range of rich-text runs, retaining surrounding run options.
 * Inserted text inherits the run at the edit boundary. Plain strings stay strings.
 * @param {string|object[]} value Original PptxGenJS text.
 * @param {string} replacement New plain text.
 * @returns {string|object[]} Text with preserved run formatting.
 */
export function editRichText(value, replacement) {
  if (Array.isArray(replacement)) return structuredClone(replacement);
  if (!Array.isArray(value)) return replacement;
  const source = value.flatMap((run) =>
    Array.from(run.text || "", (text) => ({
      text,
      options: structuredClone(run.options || {}),
    })),
  );
  const old = source.map((run) => run.text),
    next = Array.from(replacement);
  let start = 0,
    suffix = 0;
  while (
    start < old.length &&
    start < next.length &&
    old[start] === next[start]
  )
    start++;
  while (
    suffix < old.length - start &&
    suffix < next.length - start &&
    old[old.length - 1 - suffix] === next[next.length - 1 - suffix]
  )
    suffix++;
  const options = source[start]?.options || source[start - 1]?.options || {};
  const result = [
    ...source.slice(0, start),
    ...next
      .slice(start, next.length - suffix)
      .map((text) => ({ text, options })),
    ...source.slice(old.length - suffix),
  ];
  return result.reduce((runs, run) => {
    const previous = runs.at(-1);
    if (
      previous &&
      JSON.stringify(previous.options) === JSON.stringify(run.options)
    )
      previous.text += run.text;
    else runs.push({ text: run.text, options: structuredClone(run.options) });
    return runs;
  }, []);
}
