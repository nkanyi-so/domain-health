import type { Metadata } from "next";
import type { ReactElement } from "react";
import { PageFrame, ServiceStrip } from "@/components/chrome";
import { type DataRow, DataTable } from "@/components/data-table";
import { Facts, MetChip } from "@/components/parts";
import { LIMIT } from "@/content/limit";
import { repositoryUrl } from "@/lib/server/env";
import {
  EVAL_SUMMARY,
  type EvalSummary,
  MEASURES,
  type SetTotals,
  barWords,
  casesFact,
  coverageNote,
  harmfulWords,
  measureLabel,
  missedSentence,
  modelScore,
  notInUseSentence,
  promptNumber,
  score,
} from "@/lib/view/evals";
import { formatCount, formatDay } from "@/lib/view/format";

export const metadata: Metadata = { title: "Evals" };

function barRows(summary: EvalSummary): DataRow[] {
  return MEASURES.map((name) => ({
    key: name,
    cells: [
      measureLabel(name),
      barWords(summary.measures[name].bar),
      modelScore(name, summary),
      <MetChip key="result" met={summary.measures[name].met} />,
    ],
  }));
}

function setRows(label: string, totals: SetTotals, runs: number): DataRow[] {
  const set = `${label} (${totals.cases})`;
  return [
    {
      key: `${label}-coverage`,
      cells: [set, "Coverage", score(totals.coverage), score(totals.baseline_coverage)],
    },
    {
      key: `${label}-precision`,
      cells: [set, "Precision", score(totals.precision), score(totals.baseline_precision)],
    },
    {
      key: `${label}-harmful`,
      cells: [
        set,
        "Harmful",
        harmfulWords(totals.harmful, { cases: totals.cases, runs, stability: totals.stability }),
        // The rules give the same list every run, so they are counted once for each case.
        `${formatCount(totals.baseline_harmful)} in ${totals.cases} cases`,
      ],
    },
  ];
}

function notInUseRows(summary: EvalSummary): DataRow[] {
  return summary.not_in_use.map((entry) => ({
    key: entry.prompt_version,
    cells: [
      `Prompt version ${promptNumber(entry.prompt_version)}`,
      score(entry.coverage),
      score(entry.precision),
      harmfulWords(entry.harmful, {
        cases: summary.cases,
        runs: summary.runs,
        stability: entry.stability,
      }),
      score(entry.stability),
    ],
  }));
}

export default function Page(): ReactElement {
  const summary = EVAL_SUMMARY;
  const source = repositoryUrl();
  return (
    <PageFrame strip={<ServiceStrip />}>
      <div className="flex flex-col gap-8 wide:gap-12">
        <div className="flex flex-col gap-4">
          <h1 className="t-title">How the model&apos;s list scored</h1>
          <p className="t-lead measure">
            The evals were written before the prompt. They showed that a table of rules does better
            than the model on this task, so the product ships that way: rules write the fix list,
            and the model&apos;s risks are advisory.
          </p>
          <p className="t-body measure">{LIMIT}</p>
          <Facts
            facts={[
              { label: "Prompt version", value: promptNumber(summary.prompt_version) },
              { label: "Model", value: summary.model },
              { label: "Recorded", value: formatDay(summary.recorded_at) },
              { label: "Cases", value: casesFact(summary) },
            ]}
          />
        </div>

        <section aria-labelledby="bars-heading">
          <h2 id="bars-heading" className="t-heading">
            The four bars
          </h2>
          <DataTable
            caption="The four bars and the model's score on each"
            columns={["Measure", "Bar", "Model", "Result"]}
            rows={barRows(summary)}
            numeric={[1, 2]}
          />
          <p className="measure mt-3 font-medium">{missedSentence(summary)}</p>
          <p className="measure mt-1">{coverageNote(summary)}</p>
          <p className="t-small measure mt-1 text-ink-2">
            {formatCount(summary.dropped)} of the {formatCount(summary.case_runs)} answers failed
            their checks and were dropped.
          </p>
        </section>

        <section aria-labelledby="sets-heading">
          <h2 id="sets-heading" className="t-heading">
            By set, beside rules alone
          </h2>
          <DataTable
            caption="Each set's scores for the model and for rules alone"
            columns={["Set", "Measure", "Model", "Rules only"]}
            rows={[
              ...setRows("Table cases", summary.sets.table, summary.runs),
              ...setRows("Open cases", summary.sets.open, summary.runs),
            ]}
            numeric={[2, 3]}
          />
          <p className="measure mt-3">
            On the table cases the labels are the rules table&apos;s own output, so rules alone
            score full marks there by construction.
          </p>
          <p className="measure mt-1">
            {summary.better_than_baseline_on_open
              ? "On the open cases the model did better than rules alone, by the rule the harness uses for that."
              : "On the open cases the model did not do better than rules alone, by the rule the harness uses for that."}
          </p>
          <p className="t-small measure mt-1 text-ink-2">
            Rules only is the rubric&apos;s bands applied by code, with no model. It gives the same
            list on every run, so it is counted once for each case.
          </p>
        </section>

        <section aria-labelledby="not-in-use-heading">
          <h2 id="not-in-use-heading" className="t-heading">
            Not in use
          </h2>
          <DataTable
            caption="Prompt versions that were measured and are not in use"
            columns={["Prompt version", "Coverage", "Precision", "Harmful", "Stability"]}
            rows={notInUseRows(summary)}
            numeric={[1, 2, 3, 4]}
          />
          <p className="measure mt-3">
            {summary.not_in_use.map((entry) => notInUseSentence(entry, summary)).join(" ")} Did
            worse than the version in use. Why is not established.
          </p>
        </section>

        <section aria-labelledby="labels-heading" className="measure">
          <h2 id="labels-heading" className="t-heading">
            Where the labels came from
          </h2>
          <p className="mt-2">
            Drafted by AI against a written rubric and public guidance, and reviewed by the engineer
            who built the original system. Not written or reviewed by a deliverability specialist.
          </p>
          {source ? (
            <p className="mt-2">
              <a href={source} className="link">
                Read the rubric, the cases and the full results in the repository
              </a>
            </p>
          ) : null}
        </section>
      </div>
    </PageFrame>
  );
}
