interface Props {
  title: string;
  description: string;
  icon?: React.ReactNode;
  action?: React.ReactNode;
  className?: string;
}

export default function EmptyState({ title, description, icon, action, className = "" }: Props) {
  return (
    <div
      className={`flex flex-col items-center justify-center rounded-lg border-2 border-dashed border-gray-200 bg-gray-50/50 px-6 py-12 text-center ${className}`}
    >
      {icon && <div className="mb-4 text-4xl text-gray-400">{icon}</div>}
      <h3 className="text-lg font-semibold text-gray-700">{title}</h3>
      <p className="mt-2 max-w-md text-sm text-gray-500">{description}</p>
      {action && <div className="mt-6">{action}</div>}
    </div>
  );
}
