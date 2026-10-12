function Skeleton({ variant = "line", className = "", ...rest }) {
  const classes = [
    "sw-skeleton",
    `sw-skeleton--${variant}`,
    className,
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <div
      className={classes}
      aria-hidden="true"
      {...rest}
    />
  );
}

export default Skeleton;
