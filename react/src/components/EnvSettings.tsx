import {
  ProjectEnvironmentEntry,
  getProjectEnvironment,
  upsertProjectEnvironment,
  deleteProjectEnvironment,
} from "../services/api";
import { EnvSettingsModal } from "./EnvSettingsModal";

interface EnvSettingsProps {
  isOpen: boolean;
  onClose: () => void;
  projectId: string;
  projectName: string;
}

export function EnvSettings({
  isOpen,
  onClose,
  projectId,
  projectName,
}: EnvSettingsProps) {
  return (
    <EnvSettingsModal<ProjectEnvironmentEntry>
      isOpen={isOpen}
      onClose={onClose}
      title={`Environment - ${projectName}`}
      emptyMessage="No environment variables yet. Add your first one!"
      loadErrorMessage="Failed to load environment"
      loadEntries={() => getProjectEnvironment(projectId)}
      upsertEntry={(key, value, type, previousKey) =>
        upsertProjectEnvironment(projectId, key, value, type, previousKey)
      }
      deleteEntry={(key) => deleteProjectEnvironment(projectId, key)}
    />
  );
}
