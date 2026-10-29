"use client";

import * as React from "react";
import { Eraser, Loader2, Pencil } from "lucide-react";
import { t } from "@/lib/copy";
import { formatDate } from "@/lib/format";
import { useColumnMapping, useSaveColumnMapping } from "@/lib/queries-records";
import type { UploadColumn } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { Crumbs, PageHeader } from "@/components/common/page-header";
import { ErrorBlock, errorMessage } from "@/components/common/query-state";
import { useMe } from "@/components/providers/root-provider";
import { MappingProblems, MappingRows, problemsOf, type Choice } from "@/components/uploads/column-mapping";

/**
 * /college/column-mapping (page spec W4-10): how Countersign reads the
 * college's column names. Read only until Change mapping; Clear asks first.
 * Here only the saved headers are listed, so only duplicates are checked;
 * the upload checks the required columns against a whole file.
 */
export function ColumnMappingPage() {
  const { user } = useMe();
  const id = user?.scope.institution_id ?? null;
  const q = useColumnMapping(id);
  const save = useSaveColumnMapping(id ?? "");
  const [editing, setEditing] = React.useState(false);
  const [choices, setChoices] = React.useState<Record<string, Choice>>({});
  const [confirm, setConfirm] = React.useState(false);
  const [message, setMessage] = React.useState<string | null>(null);
  const firstProblem = React.useRef<HTMLSelectElement | null>(null);
  const resetButton = React.useRef<HTMLButtonElement | null>(null);
  const data = q.data;
  const headers = data ? Object.keys(data.mapping) : [];

  function startEdit() {
    if (!data) return;
    setChoices({ ...data.mapping });
    setMessage(null);
    setEditing(true);
  }

  function submit() {
    const { duplicates } = problemsOf(choices, []);
    if (duplicates.length) {
      firstProblem.current?.focus();
      return;
    }
    const mapping = Object.fromEntries(Object.entries(choices).filter(([, v]) => v)) as Record<string, UploadColumn>;
    save.mutate(
      { mapping },
      {
        onSuccess: () => {
          setEditing(false);
          setMessage(t("mapping.saved"));
        },
      },
    );
  }

  return (
    <>
      <Crumbs items={[{ label: t("nav.ledger"), href: "/college" }, { label: t("nav.upload"), href: "/college/upload" }, { label: t("mapping.settings_heading") }]} />
      <PageHeader
        title={t("mapping.settings_heading")}
        description={<p>{t("mapping.settings_lead")}</p>}
        actions={
          data &&
          headers.length > 0 &&
          !editing && (
            <>
              <Button variant="outline" className="h-11 sm:h-9" onClick={startEdit}>
                <Pencil className="size-4" aria-hidden="true" />
                {t("mapping.edit")}
              </Button>
              <Button ref={resetButton} variant="outline" className="h-11 sm:h-9" onClick={() => setConfirm(true)}>
                <Eraser className="size-4" aria-hidden="true" />
                {t("mapping.reset")}
              </Button>
            </>
          )
        }
      />
      <div aria-live="polite">{message && <p className="mb-4 text-sm text-check-pass-ink">{message}</p>}</div>
      {q.isError && !data && <ErrorBlock error={q.error} onRetry={() => q.refetch()} />}
      {!data && q.isLoading && <Skeleton className="h-48 max-w-3xl" />}
      {data && headers.length === 0 && <p className="max-w-3xl border-l-2 border-rule-margin bg-paper-raised px-4 py-3 text-sm text-ink-muted">{t("mapping.empty")}</p>}
      {data && headers.length > 0 && (
        <div className="flex max-w-3xl flex-col gap-3">
          {data.updated_at && (
            <p className="text-sm text-ink-muted">{t("mapping.batch_line", { date: formatDate(data.updated_at), name: data.updated_by?.name ?? "" })}</p>
          )}
          <MappingRows
            headers={headers}
            choices={editing ? choices : data.mapping}
            readOnly={!editing}
            onChange={(h, v) => setChoices({ ...choices, [h]: v })}
            firstProblemRef={firstProblem}
          />
          {editing && (
            <>
              <MappingProblems choices={choices} required={[]} />
              {save.isError && (
                <p role="alert" className="text-sm text-check-fail-ink">
                  {errorMessage(save.error)}
                </p>
              )}
              <div className="flex flex-col gap-2 sm:flex-row">
                <Button className="h-12 w-full sm:h-9 sm:w-auto" disabled={save.isPending} onClick={submit}>
                  {save.isPending && <Loader2 className="size-4 animate-spin" aria-hidden="true" />}
                  {t("mapping.save")}
                </Button>
                <Button variant="outline" className="h-12 w-full sm:h-9 sm:w-auto" onClick={() => setEditing(false)}>
                  {t("mapping.cancel_edit")}
                </Button>
              </div>
            </>
          )}
        </div>
      )}

      <Dialog open={confirm} onOpenChange={(next) => !next && !save.isPending && setConfirm(false)}>
        <DialogContent
          className="gap-5 bg-paper-raised sm:max-w-md"
          onCloseAutoFocus={(e) => {
            e.preventDefault();
            resetButton.current?.focus();
          }}
        >
          <DialogTitle className="font-display text-xl font-semibold">{t("mapping.reset")}</DialogTitle>
          <DialogDescription className="text-sm text-ink">{t("mapping.reset_confirm")}</DialogDescription>
          {save.isError && <p className="text-sm text-check-fail-ink">{errorMessage(save.error)}</p>}
          <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
            <Button variant="outline" className="h-11 sm:h-9" onClick={() => setConfirm(false)} disabled={save.isPending}>
              {t("mapping.cancel_edit")}
            </Button>
            <Button
              className="h-11 sm:h-9"
              disabled={save.isPending}
              onClick={() =>
                save.mutate(
                  { mapping: {} },
                  {
                    onSuccess: () => {
                      setConfirm(false);
                      setEditing(false);
                      setMessage(t("mapping.reset_done"));
                    },
                  },
                )
              }
            >
              {t("mapping.reset")}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}
