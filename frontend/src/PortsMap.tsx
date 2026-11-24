import { useEffect, useMemo } from 'react'
import {
  CircleMarker,
  MapContainer,
  Polyline,
  TileLayer,
  Tooltip,
  useMap,
} from 'react-leaflet'
import type { PortPoint } from './api'
import { formatPercent } from './format'
import 'leaflet/dist/leaflet.css'

const GREEN = '#16794c'
const RED = '#b42318'
const MUTED = '#64748b'

/** Approximate shipping lane through the Strait of Hormuz (lat, lon). */
const HORMUZ_ROUTE: [number, number][] = [
  [26.45, 55.4],
  [26.58, 55.95],
  [26.5, 56.35],
  [26.2, 56.65],
  [25.75, 56.95],
]

type Props = {
  ports: PortPoint[]
  selectedName: string | null
  onSelect: (name: string) => void
}

function FitPorts({ ports }: { ports: PortPoint[] }) {
  const map = useMap()
  const key = ports.map((p) => p.id).join('|')

  useEffect(() => {
    const pts = ports.filter((p) => p.lat != null && p.lon != null)
    if (!pts.length) return
    const lats = pts.map((p) => p.lat as number)
    const lons = pts.map((p) => p.lon as number)
    map.fitBounds(
      [
        [Math.min(...lats) - 0.35, Math.min(...lons) - 0.45],
        [Math.max(...lats) + 0.55, Math.max(...lons) + 0.55],
      ],
      { animate: false, padding: [28, 28] },
    )
  }, [map, key, ports])

  return null
}

export function PortsMap({ ports, selectedName, onSelect }: Props) {
  const mappable = useMemo(
    () => ports.filter((p) => p.lat != null && p.lon != null),
    [ports],
  )

  if (!mappable.length) {
    return <p className="note">No port coordinates available for the map.</p>
  }

  return (
    <div className="ports-map-wrap">
      <div className="ports-map-legend" aria-hidden="true">
        <span>
          <i className="legend-dot green" /> Gulf of Oman-facing (Fujairah, Khor Fakkan)
        </span>
        <span>
          <i className="legend-dot red" /> Persian Gulf-facing
        </span>
        <span>
          <i className="legend-line" /> Strait of Hormuz shipping lane
        </span>
      </div>
      <MapContainer
        className="ports-map"
        center={[25.2, 55.3]}
        zoom={7}
        scrollWheelZoom={false}
        attributionControl={false}
      >
        <TileLayer
          url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
          attribution="Tiles &copy; Esri"
        />
        <FitPorts ports={mappable} />
        <Polyline
          positions={HORMUZ_ROUTE}
          pathOptions={{
            color: '#9a6700',
            weight: 3,
            dashArray: '6 6',
            opacity: 0.85,
          }}
        >
          <Tooltip sticky>Strait of Hormuz</Tooltip>
        </Polyline>
        {mappable.map((port) => {
          const selected = port.name === selectedName
          const color = port.zone === 'green' ? GREEN : RED
          return (
            <CircleMarker
              key={port.id}
              center={[port.lat as number, port.lon as number]}
              radius={selected ? 11 : 7}
              pathOptions={{
                color: selected ? '#163a45' : color,
                weight: selected ? 3 : 1.5,
                fillColor: color,
                fillOpacity: selected ? 0.95 : 0.75,
              }}
              eventHandlers={{
                click: () => onSelect(port.name),
              }}
            >
              <Tooltip direction="top" offset={[0, -8]}>
                <strong>{port.name}</strong>
                <br />
                {port.zone === 'green' ? 'Gulf of Oman-facing' : 'Persian Gulf-facing'}
                {port.calls_vs_baseline != null
                  ? ` · ${formatPercent(port.calls_vs_baseline, 1)} vs baseline`
                  : ''}
              </Tooltip>
            </CircleMarker>
          )
        })}
      </MapContainer>
      <p className="ports-map-caption">
        <span style={{ color: MUTED }}>
          Click a port to open its series. Green ports face the Gulf of Oman (outside Hormuz);
          red ports face the Persian Gulf (inside Hormuz).
        </span>
      </p>
    </div>
  )
}
