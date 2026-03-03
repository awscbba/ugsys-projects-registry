export function Footer() {
  return (
    <footer className="bg-[#333333] text-white py-10 px-6">
      <div className="max-w-6xl mx-auto grid grid-cols-1 md:grid-cols-3 gap-8">
        {/* Brand */}
        <div>
          <div className="flex items-center gap-2 mb-3">
            <span aria-hidden="true">🌍</span>
            <span className="font-semibold text-sm">
              AWS User Group Cochabamba - Registro de Proyectos
            </span>
          </div>
          <p className="text-xs text-gray-400">
            © 2025 AWS User Group Cochabamba. Todos los derechos reservados.
          </p>
        </div>

        {/* Links */}
        <div>
          <h2 className="font-semibold text-sm mb-3 text-[#FF9900]">Enlaces</h2>
          <ul className="space-y-2 text-sm">
            <li>
              <a
                href="https://cbba.cloud.org.bo/aws"
                target="_blank"
                rel="noopener noreferrer"
                className="text-gray-300 hover:text-white transition-colors motion-reduce:transition-none focus-visible:outline focus-visible:outline-2 focus-visible:outline-[#4A90E2] focus-visible:outline-offset-2"
              >
                Sitio Principal
              </a>
            </li>
            <li>
              <a
                href="https://cbba.cloud.org.bo/aws/events"
                target="_blank"
                rel="noopener noreferrer"
                className="text-gray-300 hover:text-white transition-colors motion-reduce:transition-none focus-visible:outline focus-visible:outline-2 focus-visible:outline-[#4A90E2] focus-visible:outline-offset-2"
              >
                Eventos
              </a>
            </li>
            <li>
              <a
                href="https://cbba.cloud.org.bo/aws/contact"
                target="_blank"
                rel="noopener noreferrer"
                className="text-gray-300 hover:text-white transition-colors motion-reduce:transition-none focus-visible:outline focus-visible:outline-2 focus-visible:outline-[#4A90E2] focus-visible:outline-offset-2"
              >
                Contacto
              </a>
            </li>
          </ul>
        </div>

        {/* Social */}
        <div>
          <h2 className="font-semibold text-sm mb-3 text-[#FF9900]">Síguenos</h2>
          <div className="flex gap-4">
            <a
              href="https://www.linkedin.com/company/aws-user-group-cochabamba"
              target="_blank"
              rel="noopener noreferrer"
              aria-label="Síguenos en LinkedIn"
              className="text-gray-300 hover:text-white transition-colors motion-reduce:transition-none focus-visible:outline focus-visible:outline-2 focus-visible:outline-[#4A90E2] focus-visible:outline-offset-2"
            >
              <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
                <path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433a2.062 2.062 0 01-2.063-2.065 2.064 2.064 0 112.063 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z" />
              </svg>
            </a>
            <a
              href="https://twitter.com/awsugcbba"
              target="_blank"
              rel="noopener noreferrer"
              aria-label="Síguenos en Twitter / X"
              className="text-gray-300 hover:text-white transition-colors motion-reduce:transition-none focus-visible:outline focus-visible:outline-2 focus-visible:outline-[#4A90E2] focus-visible:outline-offset-2"
            >
              <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
                <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-4.714-6.231-5.401 6.231H2.744l7.737-8.835L1.254 2.25H8.08l4.253 5.622zm-1.161 17.52h1.833L7.084 4.126H5.117z" />
              </svg>
            </a>
          </div>
        </div>
      </div>
    </footer>
  );
}
