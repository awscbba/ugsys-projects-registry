import { useNavigate } from "react-router-dom";
import type { Project, ProjectStatus } from "@/types/project";
import { formatDate } from "@/utils/dateUtils";

const STATUS_STYLES: Record<ProjectStatus, string> = {
  pending: "bg-gray-100 text-gray-700",
  active: "bg-green-100 text-green-700",
  completed: "bg-blue-100 text-blue-700",
  cancelled: "bg-red-100 text-red-700",
};

const STATUS_LABELS: Record<ProjectStatus, string> = {
  pending: "Pendiente",
  active: "Activo",
  completed: "Completado",
  cancelled: "Cancelado",
};

interface ProjectListProps {
  projects: Project[];
}

export default function ProjectList({ projects }: ProjectListProps) {
  const navigate = useNavigate();

  return (
    <ul className="divide-y divide-gray-200 bg-white rounded-lg shadow overflow-hidden">
      {projects.map((project) => {
        const participantLabel =
          project.max_participants != null
            ? `${project.current_participants} / ${project.max_participants}`
            : `${project.current_participants}`;

        return (
          <li key={project.id} className="p-4 flex items-start gap-4">
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <h2 className="text-sm font-semibold text-gray-900 truncate">
                  {project.name}
                </h2>
                <span className="text-xs px-2 py-0.5 rounded-full bg-indigo-100 text-indigo-700">
                  {project.category}
                </span>
                <span
                  className={`text-xs px-2 py-0.5 rounded-full ${STATUS_STYLES[project.status]}`}
                >
                  {STATUS_LABELS[project.status]}
                </span>
              </div>
              <p className="mt-1 text-sm text-gray-600 line-clamp-2">
                {project.description}
              </p>
              <p className="mt-1 text-xs text-gray-500">
                {participantLabel} participantes ·{" "}
                {formatDate(project.start_date)}
                {project.end_date ? ` – ${formatDate(project.end_date)}` : ""}
              </p>
            </div>
            <button
              type="button"
              onClick={() => navigate(`/subscribe/${project.id}`)}
              className="shrink-0 rounded-md bg-indigo-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2"
            >
              Suscribirse
            </button>
          </li>
        );
      })}
    </ul>
  );
}
