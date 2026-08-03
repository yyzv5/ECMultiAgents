interface Props {
  loading: boolean;
  children: React.ReactNode;
  onClick?: () => void;
  disabled?: boolean;
  type?: "button" | "submit";
  className?: string;
}

export function LoadingButton({
  loading,
  children,
  onClick,
  disabled,
  type = "button",
  className = "",
}: Props) {
  return (
    <button
      type={type}
      className={`btn btn-primary ${className}`}
      onClick={onClick}
      disabled={loading || disabled}
    >
      {loading ? "处理中..." : children}
    </button>
  );
}