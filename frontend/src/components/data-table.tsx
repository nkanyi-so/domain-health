import type { ReactElement, ReactNode } from "react";

export interface DataRow {
  key: string;
  /** One cell per column. The first names the row. */
  cells: ReactNode[];
}

export interface DataTableProps {
  caption: string;
  columns: readonly string[];
  rows: readonly DataRow[];
  /** Columns of figures, which align right at the wide breakpoint. */
  numeric?: readonly number[];
}

/**
 * A real table at the wide breakpoint. On a phone the same rows are a list: one block per row,
 * with every other column as a labelled line, so nothing scrolls sideways.
 */
export function DataTable({ caption, columns, rows, numeric = [] }: DataTableProps): ReactElement {
  const align = (index: number): string => (numeric.includes(index) ? "text-right" : "text-left");
  return (
    <>
      <table className="sheet mt-3 hidden w-full border-separate border-spacing-0 wide:table">
        <caption className="sr-only">{caption}</caption>
        <thead>
          <tr className="t-small bg-sunk text-ink-2">
            {columns.map((column, index) => (
              <th key={column} scope="col" className={`px-4 py-2 font-medium ${align(index)}`}>
                {column}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.key}>
              {row.cells.map((cell, index) =>
                index === 0 ? (
                  <th
                    key={columns[index]}
                    scope="row"
                    className="border-t border-line px-4 py-3 text-left font-semibold"
                  >
                    {cell}
                  </th>
                ) : (
                  <td
                    key={columns[index]}
                    className={`border-t border-line px-4 py-3 ${align(index)}`}
                  >
                    {cell}
                  </td>
                ),
              )}
            </tr>
          ))}
        </tbody>
      </table>
      <ul className="sheet mt-3 wide:hidden" aria-label={caption}>
        {rows.map((row, rowIndex) => (
          <li key={row.key} className={`p-4 ${rowIndex > 0 ? "border-t border-line" : ""}`}>
            <p className="font-semibold">{row.cells[0]}</p>
            <dl className="mt-2 flex flex-col gap-1">
              {columns.slice(1).map((column, index) => (
                <div key={column} className="flex flex-wrap items-center gap-x-2">
                  <dt className="t-small text-ink-3">{column}</dt>
                  <dd>{row.cells[index + 1]}</dd>
                </div>
              ))}
            </dl>
          </li>
        ))}
      </ul>
    </>
  );
}
