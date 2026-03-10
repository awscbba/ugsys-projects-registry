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
    <article
      className="
        group relative rounded-xl overflow-hidden flex flex-col
        bg-[#1e2738] border border-white/[0.07]
        shadow-[0_4px_24px_rgba(0,0,0,0.35)]
        transition-all duration-300 ease-out
        hover:border-[#FF9900]/30
        hover:shadow-[0_8px_40px_rgba(0,0,0,0.5),0_0_24px_rgba(255,153,0,0.08)]
        hover:-translate-y-0.5
      "
    >
      {/* Thumbnail */}
      <div className="relative w-full h-44 overflow-hidden bg-[#252f42]">
        {thumbnail ? (
          <img
            src={thumbnail}
            alt={project.name}
            className="w-full h-full object-cover transition-transform duration-500 group-hover:scale-105"
          />
        ) : (
          <div
            className="w-full h-full flex items-center justify-center"
            aria-hidden="true"
          >
            {/* Gradient placeholder */}
            <div className="absolute inset-0 bg-gradient-to-br from-[#FF9900]/10 via-[#252f42] to-[#161d2b]" />
            <svg
              className="relative w-12 h-12 text-white/10"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              aria-hidden="true"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={1}
                d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"
              />
            </svg>
          </div>
        )}
        {/* Top gradient overlay for readability */}
        <div className="absolute inset-0 bg-gradient-to-t from-[#1e2738]/60 via-transparent to-transparent" />
      </div>

      <div className="p-5 flex flex-col flex-1 gap-3">
        {/* Category + Status row */}
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-xs font-medium px-2.5 py-0.5 rounded-full bg-[#FF9900]/15 text-[#FF9900] ring-1 ring-[#FF9900]/25">
            {project.category}
          </span>
          <span className={`text-xs font-medium px-2.5 py-0.5 rounded-full ${STATUS_STYLES[project.status]}`}>
            {STATUS_LABELS[project.status]}
          </span>
        </div>

        {/* Name */}
        <h2 className="text-base font-semibold text-white/90 line-clamp-2 leading-snug">
          {project.name}
        </h2>

        {/* Description */}
        <p className="text-sm text-white/50 line-clamp-3 flex-1 leading-relaxed">
          {project.description}
        </p>

        {/* Meta row */}
        <div className="flex items-center justify-between text-xs text-white/35 pt-1 border-t border-white/[0.06]">
          <span>{participantLabel}</span>
          <span>
            {formatDate(project.start_date)}
            {project.end_date ? ` – ${formatDate(project.end_date)}` : ''}
          </span>
        </div>

        {/* CTA */}
        <button
          type="button"
          onClick={() => navigate(`/subscribe/${project.id}`)}
          className="
            mt-1 w-full rounded-lg px-4 py-2.5 text-sm font-semibold
            bg-[#FF9900] text-[#161d2b]
            hover:bg-[#ffb84d]
            active:scale-[0.98]
            transition-all duration-150
            focus:outline-none focus-visible:ring-2 focus-visible:ring-[#FF9900] focus-visible:ring-offset-2 focus-visible:ring-offset-[#1e2738]
            shadow-[0_2px_12px_rgba(255,153,0,0.25)]
            hover:shadow-[0_4px_20px_rgba(255,153,0,0.4)]
          "
        >
          Suscribirse
        </button>
      </div>
    </article>
  );
}
