import { NavLink } from "react-router-dom";

import ToastHost from "./ToastHost";

const NAV_ITEMS = [
  { to: "/jobs", label: "Jobs" },
  { to: "/runs", label: "Scrape Runs" },
];

export default function Layout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen">
      <aside className="hidden md:flex w-56 flex-col bg-gray-900 text-gray-100">
        <div className="px-4 py-5 text-lg font-bold tracking-wide">JobBot</div>
        <nav className="flex-1 px-2 space-y-1">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                `block rounded px-3 py-2 text-sm font-medium transition ${
                  isActive
                    ? "bg-gray-700 text-white"
                    : "text-gray-300 hover:bg-gray-800 hover:text-white"
                }`
              }
            >
              <span className="inline-flex items-center gap-2">
                {item.label}
              </span>
            </NavLink>
          ))}
        </nav>
      </aside>

      {/* Mobile header */}
      <div className="flex flex-1 flex-col">
        <header className="md:hidden flex items-center justify-between bg-gray-900 px-4 py-3 text-white">
          <span className="text-lg font-bold">JobBot</span>
          <nav className="flex gap-3 text-sm">
            {NAV_ITEMS.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) =>
                  isActive ? "underline font-semibold" : "text-gray-300"
                }
              >
                <span className="inline-flex items-center gap-1">
                  {item.label}
                </span>
              </NavLink>
            ))}
          </nav>
        </header>

        <main className="flex-1 p-4 md:p-6 overflow-auto">{children}</main>
      </div>
      <ToastHost />
    </div>
  );
}
