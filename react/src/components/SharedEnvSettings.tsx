import {
  UserEnvironmentEntry,
  getUserEnvironment,
  upsertUserEnvironment,
  deleteUserEnvironment,
} from "../services/api";
import { EnvSettingsModal } from "./EnvSettingsModal";

interface SharedEnvSettingsProps {
  isOpen: boolean;
  onClose: () => void;
}

export function SharedEnvSettings({ isOpen, onClose }: SharedEnvSettingsProps) {
  return (
    <EnvSettingsModal<UserEnvironmentEntry>
      isOpen={isOpen}
      onClose={onClose}
      title="Shared Environment"
      emptyMessage="No shared environment variables yet. Add your first one!"
      loadErrorMessage="Failed to load shared environment"
      loadEntries={() => getUserEnvironment()}
      upsertEntry={(key, value, type, previousKey) =>
        upsertUserEnvironment(key, value, type, previousKey)
      }
      deleteEntry={(key) => deleteUserEnvironment(key)}
    />
  );
}
