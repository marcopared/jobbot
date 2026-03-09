import { useEffect, useState } from "react";

import { JOBBOT_ERROR_EVENT } from "../notify";

type Toast = {
  id: number;
  message: string;
};

export default function ToastHost() {
  const [toasts, setToasts] = useState<Toast[]>([]);

  useEffect(() => {
    let idCounter = 1;
    const onError = (event: Event) => {
      const custom = event as CustomEvent<string>;
      const message = (custom.detail || "Unexpected error").toString();
      const id = idCounter++;
      setToasts((prev) => [...prev, { id, message }]);
      window.setTimeout(() => {
        setToasts((prev) => prev.filter((t) => t.id !== id));
      }, 4000);
    };
    window.addEventListener(JOBBOT_ERROR_EVENT, onError);
    return () => window.removeEventListener(JOBBOT_ERROR_EVENT, onError);
  }, []);

  if (toasts.length === 0) return null;

  return (
    <div className="pointer-events-none fixed bottom-4 right-4 z-50 flex w-[22rem] flex-col gap-2">
      {toasts.map((toast) => (
        <div
          key={toast.id}
          className="rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700 shadow"
        >
          {toast.message}
        </div>
      ))}
    </div>
  );
}
