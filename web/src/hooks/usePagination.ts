import { useState } from 'react';

export function usePagination(total: number, pageSize: number) {
  const [page, setPage] = useState(1);
  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  function goTo(p: number) {
    setPage(Math.max(1, Math.min(p, totalPages)));
  }

  function next() {
    goTo(page + 1);
  }

  function prev() {
    goTo(page - 1);
  }

  return { page, totalPages, goTo, next, prev, setPage };
}
