import { useNavigate } from 'react-router-dom';
import type { Project, ProjectStatus } from '@/types/project';

const STATUS_STYLES: Record<ProjectStatus, string> = {
  pending: 'bg-gray-100 text-gray-700',
  active: 'bg-green-100 text-green-700',
  completed: 'bg-blue-100 text-blue-700',
  cancelled: 'bg-red-100 text-red-700',
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
    <div className="overflow-x-auto rounded-lg shadow">
      <table className="min-w-full bg-white text-sm">
        <thead className="bg-gray-50 text-xs text-gray-500 uppercase tracking-wide">
          <tr>
            <th className="px-4 py-3 text-left">Nombre</th>
            <th className="px-4 py-3 text-left">Categoría</th>
            <th className="px-4 py-3 text-left">Participantes</th>
            <th className="px-4 py-3 text-left">Estado</th>
            <th className="px-4 py-3 text-left">Acción</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100">
          {projects.map((project) => {
            const participantLabel =
              project.max_participants != null
                ? `${project.current_participants} / ${project.max_participants}`
                : `${project.current_participants}`;

            return (
              <tr key={project.id} className="hover:bg-gray-50">
                <td className="px-4 py-3 font-medium text-gray-900 max-w-xs truncate">
                  {project.name}
                </td>
                <td className="px-4 py-3 text-gray-600">{project.category}</td>
                <td className="px-4 py-3 text-gray-600">{participantLabel}</td>
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
                    className="text-indigo-600 hover:text-indigo-800 font-medium focus:outline-none focus:underline"
                  >
                    Suscribirse
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
