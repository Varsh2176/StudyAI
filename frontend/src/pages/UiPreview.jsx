/**
 * DEV-ONLY component gallery at /__ui.
 * Guarded by import.meta.env.DEV in App.jsx. Remove in Phase 7.
 */
import { useState } from "react";
import {
  Badge,
  Button,
  Card,
  EmptyState,
  ErrorMessage,
  Input,
  Modal,
  ProgressBar,
  Select,
  Skeleton,
  Textarea,
  statusToBadgeVariant,
  riskToBadgeVariant,
  priorityToBadgeVariant,
  subjectColor,
  IconDashboard,
  IconPredict,
  IconPlanner,
  IconTutor,
  IconDocuments,
  IconProgress,
  IconProfile,
  IconSend,
  IconUpload,
  IconCheck,
  IconAlert,
  IconClock,
  IconBook,
  IconSparkles,
  IconMenu,
  IconClose,
  IconRefresh,
} from "../components/ui";

function UiPreview() {
  const [modalOpen, setModalOpen] = useState(false);
  const [loading, setLoading] = useState(false);

  const subjects = ["Machine Learning", "Statistics", "Operating Systems", "Machine Learning"];

  return (
    <div className="sw-ui-preview">
      <h1>UI component preview</h1>
      <p className="sw-ui-preview-note">
        Temporary DEV route <code>/__ui</code> — remove in Phase 7. Not available in production builds.
      </p>

      <section>
        <h2>Buttons</h2>
        <div className="sw-ui-row">
          <Button variant="primary">Primary</Button>
          <Button variant="secondary">Secondary</Button>
          <Button variant="ghost">Ghost</Button>
          <Button variant="danger">Danger</Button>
          <Button size="sm">Small</Button>
          <Button
            loading={loading}
            onClick={() => {
              setLoading(true);
              window.setTimeout(() => setLoading(false), 1200);
            }}
          >
            Loading demo
          </Button>
          <Button disabled>Disabled</Button>
        </div>
      </section>

      <section>
        <h2>Card</h2>
        <Card title="Sample card" action={<Button size="sm" variant="secondary">Action</Button>} footer="Footer slot">
          Card body with StudyWise surface tokens.
        </Card>
        <Card interactive title="Interactive card">
          Hover for elevation.
        </Card>
      </section>

      <section>
        <h2>Badges</h2>
        <div className="sw-ui-row">
          <Badge variant="neutral">Neutral</Badge>
          <Badge variant="success">Success</Badge>
          <Badge variant="warning">Warning</Badge>
          <Badge variant="danger">Danger</Badge>
          <Badge variant="info">Info</Badge>
          <Badge variant="primary">Primary</Badge>
          <Badge variant={riskToBadgeVariant("Low Risk")}>Low Risk</Badge>
          <Badge variant={priorityToBadgeVariant("High Priority")}>High Priority</Badge>
          <Badge variant={statusToBadgeVariant("missed")}>missed</Badge>
          <Badge variant={statusToBadgeVariant("completed")}>completed</Badge>
        </div>
      </section>

      <section>
        <h2>Fields</h2>
        <Input label="Email" hint="Stored locally as student identity" placeholder="you@college.edu" />
        <Input label="With error" error="This field is required" defaultValue="" />
        <Select label="Status" hint="Session outcome" defaultValue="completed">
          <option value="completed">Completed</option>
          <option value="partial">Partial</option>
          <option value="missed">Missed</option>
        </Select>
        <Textarea label="Notes" hint="Optional" placeholder="Write something…" />
        <Input label="Disabled" disabled defaultValue="Cannot edit" />
      </section>

      <section>
        <h2>Modal</h2>
        <Button variant="secondary" onClick={() => setModalOpen(true)}>
          Open modal
        </Button>
        <Modal
          open={modalOpen}
          title="Example dialog"
          onClose={() => setModalOpen(false)}
          footer={
            <>
              <Button variant="ghost" onClick={() => setModalOpen(false)}>
                Cancel
              </Button>
              <Button onClick={() => setModalOpen(false)}>Confirm</Button>
            </>
          }
        >
          Press Esc or click the backdrop to close. Tab should cycle inside the dialog.
        </Modal>
      </section>

      <section>
        <h2>Skeleton</h2>
        <Skeleton variant="line" />
        <Skeleton variant="block" />
        <Skeleton variant="card" />
      </section>

      <section>
        <h2>Error & empty</h2>
        <ErrorMessage message="Something went wrong loading data." onRetry={() => {}} />
        <EmptyState
          title="Nothing here yet"
          description="Empty states must not invent statistics — only guide the next action."
          action={<Button size="sm">Primary action</Button>}
        />
      </section>

      <section>
        <h2>Progress</h2>
        <ProgressBar value={72} label="Completion" color="primary" />
        <ProgressBar value={40} label="Fulfillment" color="warning" />
        <ProgressBar value={90} label="Attendance" color="success" />
      </section>

      <section>
        <h2>Icons</h2>
        <div className="sw-ui-row" style={{ color: "var(--sw-primary)" }}>
          <IconDashboard />
          <IconPredict />
          <IconPlanner />
          <IconTutor />
          <IconDocuments />
          <IconProgress />
          <IconProfile />
          <IconSend />
          <IconUpload />
          <IconCheck />
          <IconAlert />
          <IconClock />
          <IconBook />
          <IconSparkles />
          <IconMenu />
          <IconClose />
          <IconRefresh />
        </div>
      </section>

      <section>
        <h2>subjectColor</h2>
        <div className="sw-ui-row">
          {subjects.map((name, idx) => {
            const c = subjectColor(name);
            return (
              <span
                key={`${name}-${idx}`}
                className="sw-ui-subject-swatch"
                style={{ background: c.soft, color: c.solid }}
              >
                {name}
              </span>
            );
          })}
        </div>
        <p style={{ fontSize: "var(--sw-text-xs)", color: "var(--sw-text-muted)" }}>
          Both “Machine Learning” chips must match (deterministic).
        </p>
      </section>
    </div>
  );
}

export default UiPreview;
