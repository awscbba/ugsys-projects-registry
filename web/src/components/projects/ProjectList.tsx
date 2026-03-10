import { useNavigate } from 'react-router-dom';
import type { Project, ProjectStatus } from '@/types/project';
import { formatDate } from '@/utils/dateUtils';

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

interface ProjectListProps {
  projects: Project[];
}

export default function ProjectList({ projects }: ProjectListProps) {
  const navigate = useNavigate();

  return (
    <ul className="flex flex-col gap-2">
      {projects.map((project) => {
        const participantLabel =
          project.max_participants != null
            ? `${project.current_participants} / ${project.max_participants}`
            : `${project.current_participants}`;

        return (
          <li
            key={project.id}
            className="
              flex items-start gap-4 p-4 rounded-xl
              bg-[#1e2738] border border-white/[0.07]
              shadow-[0_2px_12px_rgba(0,0,0,0.25)]
              transition-all duration-200
              hover:border-[#FF9900]/25
              hover:shadow-[0_4px_24px_rgba(0,0,0,0.35)]
            "
          >
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 flex-wrap mb-1">
                <h2 className="text-sm font-semibold text-white/90 truncate">{project.name}</h2>
                <span className="text-xs px-2 py-0.5 rounded-full bg-[#FF9900]/15 text-[#FF9900] ring-1 ring-[#FF9900]/25">
                  {project.category}
                </span>
                <span
                  className={`text-xs px-2 py-0.5 rounded-full ${STATUS_STYLES[project.status]}`}
                >
                  {STATUS_LABELS[project.status]}
                </span>
              </div>
              <p className="text-sm text-white/50 line-clamp-2 leading-relaxed">
                {project.description}
              </p>
              <p className="mt-1.5 text-xs text-white/30">
                {participantLabel} participantes · {formatDate(project.start_date)}
                {project.end_date ? ` – ${formatDate(project.end_date)}` : ''}
              </p>
            </div>
            <button
              type="button"
              onClick={() => navigate(`/subscribe/${project.id}`)}
              className="
                shrink-0 rounded-lg px-3.5 py-1.5 text-xs font-semibold
                bg-[#FF9900] text-[#161d2b]
                hover:bg-[#ffb84d]
                active:scale-[0.97]
                transition-all duration-150
                focus:outline-none focus-visible:ring-2 focus-visible:ring-[#FF9900] focus-visible:ring-offset-2 focus-visible:ring-offset-[#1e2738]
                shadow-[0_2px_8px_rgba(255,153,0,0.2)]
              "
            >
              Suscribirse
            </button>
          </li>
        );
      })}
    </ul>
  );
}
