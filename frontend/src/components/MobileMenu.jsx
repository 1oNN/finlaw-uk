import { NavLink } from "react-router-dom";
import { FaTimes } from "react-icons/fa";
import { motion, AnimatePresence } from "framer-motion";

export default function MobileMenu({ open, onClose }) {
  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.div
            className="fixed inset-0 z-40 bg-black/50"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
          />
          <motion.aside
            className="fixed right-0 top-0 z-50 h-full w-72 border-l border-white/15 bg-panel p-4"
            initial={{ x: 288 }}
            animate={{ x: 0 }}
            exit={{ x: 288 }}
            transition={{ type: "tween" }}
          >
            <div className="mb-4 flex items-center justify-between">
              <span className="font-semibold text-white">Menu</span>
              <button
                onClick={onClose}
                className="rounded-md border border-white/15 p-2 text-gray-300 hover:bg-white/10"
              >
                <FaTimes />
              </button>
            </div>

            <nav className="flex flex-col gap-2">
              <NavLink
                to="/"
                end
                className="rounded-lg px-3 py-2 text-white hover:bg-white/10"
                onClick={onClose}
              >
                Home
              </NavLink>
              <NavLink
                to="/chat"
                className="rounded-lg px-3 py-2 text-white hover:bg-white/10"
                onClick={onClose}
              >
                Chat
              </NavLink>
              <NavLink
                to="/pricing"
                className="rounded-lg px-3 py-2 text-white hover:bg-white/10"
                onClick={onClose}
              >
                Pricing
              </NavLink>
            </nav>
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  );
}
