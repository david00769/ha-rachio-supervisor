const revealed = document.querySelectorAll(".reveal");

const observer = new IntersectionObserver(
  (entries) => {
    for (const entry of entries) {
      if (entry.isIntersecting) {
        entry.target.classList.add("in");
      }
    }
  },
  { threshold: 0.18 }
);

revealed.forEach((node) => observer.observe(node));

