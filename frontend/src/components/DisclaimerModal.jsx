import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { FiX } from "react-icons/fi";
import Logo from "./Logo";

export default function DisclaimerModal() {
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (!localStorage.getItem("disclaimerAccepted")) setOpen(true);
  }, []);

  const accept = () => {
    localStorage.setItem("disclaimerAccepted", "true");
    setOpen(false);
  };

  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.div
            className="fixed inset-0 z-40 bg-ink/40 backdrop-blur-sm"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={accept}
          />
          <motion.div
            role="dialog"
            aria-modal="true"
            className="fixed inset-x-0 bottom-6 z-50 mx-auto w-[calc(100%-2rem)] max-w-md overflow-hidden rounded-card border border-ivory-3 bg-white shadow-chat"
            initial={{ y: 40, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            exit={{ y: 40, opacity: 0 }}
          >
            <div className="flex items-start gap-4 p-6">
              <Logo variant="mark" size="md" />
              <div className="flex-1">
                <div className="font-display text-lg font-semibold text-ink">
                  A note before you start
                </div>
                <p className="mt-1.5 text-sm text-slate">
                  FinLaw is a research tool. Information provided is for
                  educational purposes only and{" "}
                  <span className="font-medium text-ink">
                    does not constitute legal advice
                  </span>
                  . Always cross-check generated citations against the
                  primary source.
                </p>
              </div>
              <button
                type="button"
                onClick={accept}
                className="grid h-8 w-8 flex-none place-items-center rounded-md text-slate hover:bg-ivory-2"
                aria-label="Dismiss"
              >
                <FiX size={16} />
              </button>
            </div>
            <div className="flex items-center justify-end gap-2 border-t border-ivory-3 bg-ivory-2/40 px-6 py-3">
              <button
                onClick={accept}
                className="rounded-lg bg-ink px-4 py-2 text-sm font-medium text-ivory hover:bg-ink-2"
              >
                I understand
              </button>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
