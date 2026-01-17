/**
 * UnitFilter component with multi-select dropdown.
 */
import { useState, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useFilters } from '../../context/FilterContext';
import { fetchUnits } from '../../services/unitsApi';

interface Unit {
  id: string;
  unit_name: string;
  unit_code: string;
}

export function UnitFilter() {
  const { filters, setUnitId } = useFilters();
  const navigate = useNavigate();
  const location = useLocation();
  const [units, setUnits] = useState<Unit[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  // Check if we're on the overview page
  const isOverviewPage = location.pathname === '/';

  useEffect(() => {
    const loadUnits = async () => {
      try {
        setLoading(true);
        const data = await fetchUnits();
        setUnits(data);
        setError(null);
      } catch (err) {
        console.error('Failed to load units:', err);
        setError('Failed to load units');
      } finally {
        setLoading(false);
      }
    };

    loadUnits();
  }, []);

  const handleUnitChange = (event: React.ChangeEvent<HTMLSelectElement>) => {
    const value = event.target.value;
    setUnitId(value === '' ? undefined : value);
  };

  const handleViewUnitDetails = () => {
    if (filters.unitId) {
      navigate(`/units/${filters.unitId}`);
    }
  };

  if (loading) {
    return (
      <div className="unit-filter">
        <label className="filter-label">Unit</label>
        <select className="unit-select" disabled>
          <option>Loading units...</option>
        </select>
      </div>
    );
  }

  if (error) {
    return (
      <div className="unit-filter">
        <label className="filter-label">Unit</label>
        <select className="unit-select" disabled>
          <option>Error loading units</option>
        </select>
      </div>
    );
  }

  return (
    <div className="unit-filter">
      <label htmlFor="unit-select" className="filter-label">Unit</label>
      <div className="unit-filter-controls">
        <select
          id="unit-select"
          className="unit-select"
          value={filters.unitId || ''}
          onChange={handleUnitChange}
        >
          <option value="">All Units</option>
          {units.map((unit) => (
            <option key={unit.id} value={unit.id}>
              {unit.unit_name} ({unit.unit_code})
            </option>
          ))}
        </select>
        {isOverviewPage && filters.unitId && (
          <button
            className="view-unit-details-btn"
            onClick={handleViewUnitDetails}
            title="View unit performance details"
          >
            View Details →
          </button>
        )}
      </div>
    </div>
  );
}
