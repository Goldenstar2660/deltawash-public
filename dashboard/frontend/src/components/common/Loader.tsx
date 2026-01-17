/**
 * Loader component with spinner animation.
 */

export function Loader() {
  return (
    <div className="loader-container">
      <div className="loader-spinner"></div>
      <p className="loader-text">Loading...</p>
    </div>
  );
}
