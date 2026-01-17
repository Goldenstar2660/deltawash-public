/**
 * Filters section component - groups all filter components together.
 */
import { DateRangeFilter } from './DateRangeFilter';
import { UnitFilter } from './UnitFilter';
import { ShiftFilter } from './ShiftFilter';
import { QualityToggle } from './QualityToggle';
import './Filters.css';

export function Filters() {
  return (
    <div className="filters-container">
      <h2 className="filters-title">Filters</h2>
      <div className="filters-grid">
        <DateRangeFilter />
        <UnitFilter />
        <ShiftFilter />
        <QualityToggle />
      </div>
    </div>
  );
}
