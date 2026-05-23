import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";

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
            className="fixed inset-0 z-40 bg-black/60"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
          />
          <motion.div
            className="fixed inset-x-0 bottom-8 z-50 mx-auto w-full max-w-md rounded-2xl border border-white/15 bg-panel p-5 shadow-chat"
            initial={{ y: 50, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            exit={{ y: 50, opacity: 0 }}
          >
            <p className="mb-3 text-sm text-gray-300">
              Information provided by this assistant is for educational purposes
              only and <strong>does not constitute legal advice.</strong>
            </p>
            <button
              onClick={accept}
              className="w-full rounded-lg bg-accent px-4 py-2 font-semibold text-white hover:bg-accent-hover"
            >
              I understand
            </button>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
