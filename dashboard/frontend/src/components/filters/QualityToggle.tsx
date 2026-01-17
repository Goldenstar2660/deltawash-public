/**
 * QualityToggle component for excluding low-quality sessions.
 */
import { useFilters } from '../../context/FilterContext';

export function QualityToggle() {
  const { filters, setExcludeLowQuality } = useFilters();

  return (
    <div className="quality-toggle">
      <label className="filter-label">Quality Filter</label>
      <label className="toggle-label">
        <input
          type="checkbox"
          checked={filters.excludeLowQuality}
          onChange={(e) => setExcludeLowQuality(e.target.checked)}
          className="toggle-checkbox"
        />
        <span className="toggle-text">Exclude Low Quality</span>
        <span className="toggle-description">
          (poor detection confidence)
        </span>
      </label>
    </div>
  );
}
