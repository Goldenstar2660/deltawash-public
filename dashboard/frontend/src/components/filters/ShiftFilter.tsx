/**
 * ShiftFilter component for filtering by time shift.
 */
import { useFilters } from '../../context/FilterContext';

const SHIFTS = [
  { value: 'morning', label: 'Morning', time: '7am-3pm' },
  { value: 'afternoon', label: 'Afternoon', time: '3pm-11pm' },
  { value: 'night', label: 'Night', time: '11pm-7am' },
];

export function ShiftFilter() {
  const { filters, setShift } = useFilters();

  const handleShiftClick = (shift: string) => {
    if (filters.shift === shift) {
      setShift(undefined); // Deselect if already selected
    } else {
      setShift(shift as 'morning' | 'afternoon' | 'night');
    }
  };

  return (
    <div className="shift-filter">
      <label className="filter-label">Shift</label>
      <div className="shift-buttons">
        <button
          onClick={() => setShift(undefined)}
          className={`shift-button ${filters.shift === undefined ? 'active' : ''}`}
          type="button"
        >
          All Shifts
        </button>
        {SHIFTS.map((shift) => (
          <button
            key={shift.value}
            onClick={() => handleShiftClick(shift.value)}
            className={`shift-button ${filters.shift === shift.value ? 'active' : ''}`}
            type="button"
            title={shift.time}
          >
            {shift.label}
            <span className="shift-time">{shift.time}</span>
          </button>
        ))}
      </div>
    </div>
  );
}
