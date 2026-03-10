import { useNavigate } from 'react-router-dom';
import type { Project, ProjectStatus } from '@/types/project';

const STATUS_STYLES: Record<ProjectStatus, string> = {
  pending: 'bg-yellow-500/15 text-yellow-300 ring-1 ring-yellow-500/30',
  active: 'bg-emerald-500/15 text-emerald-300 ring-1 ring-emerald-500/30',
  completed: 'bg-sky-500/15 text-sky-300 ring-1 ring-sky-500/30',
  cancelled: 'bg-red-500/15 text-red-300 ring-1 ring-red-500/30',
};

const STATUS_LABELS: Record<ProjectStatus, string> = {
  pending: 'Pendiente',
  active: 'Activo',
  completed: 'Completado',
  cancelled: 'Cancelado',
};

interface ProjectCompactProps {
  projects: Project[];
}

export default function ProjectCompact({ projects }: ProjectCompactProps) {
  const navigate = useNavigate();

  return (
    <div className="overflow-x-auto rounded-xl border border-white/[0.07] shadow-[0_4px_24px_rgba(0,0,0,0.35)]">
      <table className="min-w-full text-sm">
        <thead>
          <tr className="bg-[#252f42] border-b border-white/[0.07]">
            <th className="px-4 py-3 text-left text-xs font-semibold text-white/40 uppercase tracking-wider">
              Nombre
            </th>
            <th className="px-4 py-3 text-left text-xs font-semibold text-white/40 uppercase tracking-wider">
              Categoría
            </th>
            <th className="px-4 py-3 text-left text-xs font-semibold text-white/40 uppercase tracking-wider">
              Participantes
            </th>
            <th className="px-4 py-3 text-left text-xs font-semibold text-white/40 uppercase tracking-wider">
              Estado
            </th>
            <th className="px-4 py-3 text-left text-xs font-semibold text-white/40 uppercase tracking-wider">
              Acción
            </th>
          </tr>
        </thead>
        <tbody className="bg-[#1e2738] divide-y divide-white/[0.05]">
          {projects.map((project) => {
            const participantLabel =
              project.max_participants != null
                ? `${project.current_participants} / ${project.max_participants}`
                : `${project.current_participants}`;

            return (
              <tr key={project.id} className="transition-colors duration-150 hover:bg-[#252f42]">
                <td className="px-4 py-3 font-medium text-white/85 max-w-xs truncate">
                  {project.name}
                </td>
                <td className="px-4 py-3 text-white/50">{project.category}</td>
                <td className="px-4 py-3 text-white/50">{participantLabel}</td>
                <td className="px-4 py-3">
                  <span
                    className={`text-xs px-2 py-0.5 rounded-full font-medium ${STATUS_STYLES[project.status]}`}
                  >
                    {STATUS_LABELS[project.status]}
                  </span>
                </td>
                <td className="px-4 py-3">
                  <button
                    type="button"
                    onClick={() => navigate(`/subscribe/${project.id}`)}
                    className="
                      text-[#FF9900] hover:text-[#ffb84d] font-semibold text-xs
                      transition-colors duration-150
                      focus:outline-none focus-visible:underline
                    "
                  >
                    Suscribirse →
                  </button>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
