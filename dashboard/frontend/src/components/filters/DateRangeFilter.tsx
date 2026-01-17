/**
 * DateRangeFilter component with preset date ranges.
 */
import { useFilters } from '../../context/FilterContext';

const DATE_PRESETS = [
  { label: 'Last 24 Hours', days: 1 },
  { label: 'Last 7 Days', days: 7 },
  { label: 'Last 30 Days', days: 30 },
  { label: 'Last 90 Days', days: 90 },
  { label: 'Last Year', days: 365 },
];

export function DateRangeFilter() {
  const { filters, setDateRange } = useFilters();

  const handlePreset = (days: number) => {
    const to = new Date();
    const from = new Date();
    from.setDate(from.getDate() - days);
    setDateRange(from, to);
  };

  const handleCustomDate = (field: 'from' | 'to', value: string) => {
    const newDate = new Date(value);
    if (field === 'from') {
      setDateRange(newDate, filters.dateTo);
    } else {
      setDateRange(filters.dateFrom, newDate);
    }
  };

  const formatDateForInput = (date: Date) => {
    return date.toISOString().split('T')[0];
  };

  return (
    <div className="date-range-filter">
      <label className="filter-label">Date Range</label>
      
      <div className="preset-buttons">
        {DATE_PRESETS.map((preset) => (
          <button
            key={preset.label}
            onClick={() => handlePreset(preset.days)}
            className="preset-button"
            type="button"
          >
            {preset.label}
          </button>
        ))}
      </div>

      <div className="custom-date-inputs">
        <div className="date-input-group">
          <label htmlFor="date-from">From</label>
          <input
            id="date-from"
            type="date"
            value={formatDateForInput(filters.dateFrom)}
            onChange={(e) => handleCustomDate('from', e.target.value)}
            className="date-input"
          />
        </div>
        <div className="date-input-group">
          <label htmlFor="date-to">To</label>
          <input
            id="date-to"
            type="date"
            value={formatDateForInput(filters.dateTo)}
            onChange={(e) => handleCustomDate('to', e.target.value)}
            className="date-input"
          />
        </div>
      </div>
    </div>
  );
}
