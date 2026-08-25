interface LoaderProps {
  size?: number;
  fullScreen?: boolean;
  className?: string;
  alt?: string;
}

export function Loader({ size = 48, fullScreen = false, className, alt = "Loading..." }: LoaderProps) {
  return (
    <div className={`loader-container ${fullScreen ? "loader-fullscreen" : ""} ${className ?? ""}`.trim()}>
      <img src="/loader.svg" alt={alt} width={size} height={size} className="loader-image" />
    </div>
  );
}

export default Loader;
