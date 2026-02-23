import clsx from "clsx";

export function RunStatusPill({ status }: { status: string }) {
  return (
    <span
      className={clsx("status-pill", {
        pending: status === "PENDING",
        running: status === "RUNNING",
        success: status === "SUCCESS",
        failed: status === "FAILED"
      })}
    >
      {status}
    </span>
  );
}
