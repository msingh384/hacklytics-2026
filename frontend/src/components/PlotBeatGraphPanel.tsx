import { useCallback, useEffect, useRef, useState } from 'react';
import cytoscape, { type NodeSingular } from 'cytoscape';
import { api } from '../api/client';
import type { GraphResponse } from '../types/api';

/* Match app palette: accent-soft #78824b, accent #595f39, gold #c8a96e */
const NODE_COLORS: Record<string, string> = {
  MOVIE: '#78824b',
  PLOT_BEAT: '#b8a060',
  CHARACTER: '#5a7a6a',
  CLUSTER: '#6a5a7a',
  default: '#5a5a5a',
};

type Props = {
  movieId: string;
  movieTitle: string;
  onClose: () => void;
};

export function PlotBeatGraphPanel({ movieId, movieTitle, onClose }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const cyRef = useRef<cytoscape.Core | null>(null);
  const [graph, setGraph] = useState<GraphResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [detail, setDetail] = useState<{ label: string; text?: string; type?: string } | null>(null);

  const fetchGraph = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.getPlotBeatGraph(movieId);
      setGraph(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load graph');
      setGraph(null);
    } finally {
      setLoading(false);
    }
  }, [movieId]);

  useEffect(() => {
    fetchGraph();
  }, [fetchGraph]);

  useEffect(() => {
    if (!graph || !containerRef.current || graph.nodes.length === 0) return;

    const elements = [
      ...graph.nodes.map((n) => ({
        group: 'nodes' as const,
        data: { ...n.data, id: n.data.id },
      })),
      ...graph.edges.map((e) => ({
        group: 'edges' as const,
        data: {
          ...e.data,
          id: e.data.id,
        },
      })),
    ];

    const cy = cytoscape({
      container: containerRef.current,
      elements,
      style: [
        {
          selector: 'node',
          style: {
            width: (node: NodeSingular) => (node.data('type') === 'MOVIE' ? 32 : 26),
            height: (node: NodeSingular) => (node.data('type') === 'MOVIE' ? 32 : 26),
            'background-color': (node: NodeSingular) =>
              NODE_COLORS[node.data('type') as string] ?? NODE_COLORS.default,
            'border-width': 1,
            'border-color': 'rgba(255,255,255,0.3)',
            label: 'data(label)',
            'text-valign': 'bottom',
            'text-halign': 'center',
            'font-size': '10px',
            color: '#e4e4de',
            'text-outline-color': '#0d0d0d',
            'text-outline-width': 3,
            'text-max-width': '80px',
            'text-wrap': 'ellipsis',
          },
        },
        {
          selector: 'edge',
          style: {
            'curve-style': 'bezier',
            'target-arrow-color': 'rgba(228, 228, 222, 0.4)',
            'target-arrow-shape': 'triangle',
            'line-color': 'rgba(228, 228, 222, 0.3)',
            width: 1.2,
            label: 'data(label)',
            'font-size': '8px',
            color: 'rgba(228, 228, 222, 0.6)',
          },
        },
      ],
      layout: {
        name: 'cose',
        animate: false,
        idealEdgeLength: 100,
        nodeOverlap: 20,
        nodeRepulsion: 6000,
        padding: 40,
      },
    });

    cy.on('tap', 'node', (ev) => {
      const node = ev.target;
      const nodeData = node.data();
      const label = (nodeData.label as string) ?? 'Node';
      const type = nodeData.type as string;
      const beatText = nodeData.beat_text as string | undefined;
      const analysis = nodeData.analysis as string | undefined;
      const text = beatText ?? analysis;
      setDetail({ label, text, type });
    });

    cyRef.current = cy;
    return () => {
      cy.destroy();
      cyRef.current = null;
    };
  }, [graph, movieId]);

  const hasGraph = graph && graph.nodes.length > 0;

  return (
    <div className="knowledge-graph-overlay" role="dialog" aria-label="Plot Beat Graph">
      <div className="knowledge-graph-panel">
        <div className="knowledge-graph-header">
          <h2>Plot Beat Graph: {movieTitle}</h2>
          <button type="button" className="knowledge-graph-close" onClick={onClose} aria-label="Close">
            ×
          </button>
        </div>

        {loading ? (
          <p>Loading graph...</p>
        ) : error ? (
          <p className="error">{error}</p>
        ) : !hasGraph ? (
          <div className="knowledge-graph-ingest">
            <p>Run analysis on this movie to see the plot beat graph (beats, characters, clusters).</p>
          </div>
        ) : (
          <div className="knowledge-graph-content">
            <div className="knowledge-graph-cy-wrap">
              <div ref={containerRef} className="knowledge-graph-cy" />
            </div>
            <div className="knowledge-graph-evidence-wrap">
              {detail ? (
                <div className="knowledge-graph-evidence">
                  <h3>
                    {detail.label}
                    {detail.type ? ` (${detail.type})` : ''}
                  </h3>
                  {detail.text ? <p>{detail.text}</p> : <p>Click a node to see details</p>}
                </div>
              ) : (
                <div className="knowledge-graph-evidence-placeholder">
                  Click a node to see beat text or character analysis
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
