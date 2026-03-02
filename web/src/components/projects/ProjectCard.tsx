import { useNavigate } from 'react-router-dom';
import type { Project, ProjectStatus } from '@/types/project';
import { formatDate } from '@/utils/dateUtils';

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

interface ProjectCardProps {
  project: Project;
}

export default function ProjectCard({ project }: ProjectCardProps) {
  const navigate = useNavigate();
  const thumbnail = project.images?.[0]?.cloudfront_url;

  const participantLabel =
    project.max_participants != null
      ? `${project.current_participants} / ${project.max_participants} participantes`
      : `${project.current_participants} participantes`;

  return (
    <article className="rounded-lg shadow overflow-hidden bg-white flex flex-col">
      {/* Thumbnail */}
      {thumbnail ? (
        <img src={thumbnail} alt={project.name} className="w-full h-40 object-cover" />
      ) : (
        <div className="w-full h-40 bg-gray-200" aria-hidden="true" />
      )}

      <div className="p-4 flex flex-col flex-1 gap-2">
        {/* Category badge */}
        <span className="self-start text-xs font-medium px-2 py-0.5 rounded-full bg-indigo-100 text-indigo-700">
          {project.category}
        </span>

        {/* Name */}
        <h2 className="text-base font-semibold text-gray-900 line-clamp-2">{project.name}</h2>

        {/* Description */}
        <p className="text-sm text-gray-600 line-clamp-3 flex-1">{project.description}</p>

        {/* Participants */}
        <p className="text-xs text-gray-500">{participantLabel}</p>

        {/* Date range */}
        <p className="text-xs text-gray-500">
          {formatDate(project.start_date)}
          {project.end_date ? ` – ${formatDate(project.end_date)}` : ''}
        </p>

        {/* Status badge */}
        <span
          className={`self-start text-xs font-medium px-2 py-0.5 rounded-full ${STATUS_STYLES[project.status]}`}
        >
          {STATUS_LABELS[project.status]}
        </span>

        {/* Subscribe button */}
        <button
          type="button"
          onClick={() => navigate(`/subscribe/${project.id}`)}
          className="mt-auto w-full rounded-md bg-indigo-600 px-3 py-2 text-sm font-medium text-white hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2"
        >
          Suscribirse
        </button>
      </div>
    </article>
  );
}
